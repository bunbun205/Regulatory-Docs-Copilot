import asyncio
import json
from dataclasses import asdict

import httpx
import pytest

from app.gapcheck.judge import GapCheckJudge, JudgeFailure
from app.llm.base import LLMMessage, TokenUsage
from app.llm.budget import TokenBudget, TokenBudgetExceeded, active_token_budget
from app.llm.fake import FakeLLM, FakeResponse
from app.llm.openai_compat import OpenAICompatibleClient
from tests.unit.test_gapcheck_judge import _hit
from tests.unit.test_gapcheck_runner import SOP_TEXT, StubRetriever, _runner


def test_reservations_are_conservative_and_never_double_spend():
    budget = TokenBudget(2500)
    first = budget.reserve({"text": "🙂"}, 100)
    second = budget.reserve({"text": "🙂"}, 100)
    with pytest.raises(TokenBudgetExceeded):
        budget.reserve({"text": "🙂"}, 100)
    assert budget.charged_tokens == first + second <= budget.limit
    budget.settle(first, TokenUsage(20, 10))
    assert budget.charged_tokens == second + 30
    assert budget.unreported_tokens == second
    assert budget.usage.total_tokens == 30


def test_provider_overrun_is_reported_and_stops_further_calls():
    budget = TokenBudget(5000)
    amount = budget.reserve({}, 100)
    with pytest.raises(TokenBudgetExceeded):
        budget.settle(amount, TokenUsage(6000, 1))
    assert budget.usage.total_tokens == 6001
    assert budget.charged_tokens == 6001
    assert budget.provider_overrun
    with pytest.raises(TokenBudgetExceeded):
        budget.reserve({}, 1)


async def test_validation_failures_preserve_both_attempts_usage():
    llm = FakeLLM([FakeResponse(text="invalid", usage=TokenUsage(80, 20))] * 2)
    judge = GapCheckJudge(llm)
    judge.budget = TokenBudget(20000)
    with pytest.raises(JudgeFailure) as exc:
        await judge.judge_clause(
            clause_id="SOP-001", clause_text="retain records", section="", retrieved_hits=[_hit()]
        )
    assert exc.value.usage.total_tokens == 200
    assert judge.budget.usage.total_tokens == 200
    assert judge.budget.charged_tokens == 200
    assert len(llm.requests) == 2


async def test_concurrent_judgements_reserve_before_call_and_cache_is_free():
    hit = _hit()
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingLLM(FakeLLM):
        async def chat(self, messages, **kwargs):
            started.set()
            await release.wait()
            return await super().chat(messages, **kwargs)

    llm = BlockingLLM(
        [
            FakeResponse(
                text=json.dumps(
                    {
                        "verdict": "compliant",
                        "citations": [str(hit.chunk_id)],
                        "rationale": "Evidence.",
                    }
                ),
                usage=TokenUsage(80, 20),
            )
        ]
    )
    judge = GapCheckJudge(llm)
    # Probe the exact admission cost using the same generated prompt, without a network call.
    probe = FakeLLM([FakeResponse(text="bad")] * 2)
    probe_judge = GapCheckJudge(probe)
    with pytest.raises(JudgeFailure):
        await probe_judge.judge_clause(
            clause_id="SOP-001", clause_text="retain records", section="", retrieved_hits=[hit]
        )
    reservation = TokenBudget(100000).reserve(
        [asdict(m) for m in probe.requests[0]["messages"]], judge.max_tokens
    )
    judge.budget = TokenBudget(reservation)
    kwargs = {
        "clause_id": "SOP-001",
        "clause_text": "retain records",
        "section": "",
        "retrieved_hits": [hit],
    }
    first = asyncio.create_task(judge.judge_clause(**kwargs))
    await started.wait()
    others = await asyncio.gather(
        *(judge.judge_clause(**kwargs) for _ in range(3)), return_exceptions=True
    )
    assert all(
        isinstance(result, JudgeFailure) and result.reason == "token_cap" for result in others
    )
    release.set()
    assert (await first).verdict == "compliant"
    judge.budget.limit = judge.budget.charged_tokens
    assert (await judge.judge_clause(**kwargs)).cached
    assert len(llm.requests) == 1
    assert judge.budget.usage.total_tokens == 100
    assert judge.budget.charged_tokens == 100


@pytest.mark.parametrize("status", [429, 500, "timeout"])
async def test_provider_retries_reserve_unknown_attempt_before_resending(status):
    calls = []

    def handler(request):
        calls.append(request)
        if status == "timeout":
            raise httpx.ReadTimeout("test timeout", request=request)
        return httpx.Response(status, json={"error": "temporary failure"})

    async def sleep(_):
        pass

    client = OpenAICompatibleClient(
        base_url="http://llm.local/v1",
        model="test",
        max_retries=3,
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    budget = TokenBudget(2000)
    token = active_token_budget.set(budget)
    try:
        with pytest.raises(TokenBudgetExceeded):
            await client.chat([LLMMessage(role="user", content="hello")], max_tokens=64)
    finally:
        active_token_budget.reset(token)
        await client.close()
    assert len(calls) == 1
    assert budget.attempts == 1
    assert 0 < budget.unreported_tokens == budget.charged_tokens <= 2000


async def test_unknown_usage_retains_reservation():
    client = OpenAICompatibleClient(
        base_url="http://llm.local/v1",
        model="test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "hello"}}]}
            )
        ),
    )
    budget = TokenBudget(2000)
    token = active_token_budget.set(budget)
    try:
        await client.chat([LLMMessage(role="user", content="hello")], max_tokens=64)
    finally:
        active_token_budget.reset(token)
        await client.close()
    assert budget.usage.total_tokens == 0
    assert budget.unreported_tokens == budget.charged_tokens > 0


async def test_runner_reports_failed_validation_usage():
    judge = GapCheckJudge(FakeLLM([FakeResponse(text="invalid", usage=TokenUsage(80, 20))] * 8))
    report = await _runner(StubRetriever([_hit()]), judge).run(SOP_TEXT)
    assert all(f["verdict"] == "judge_failed" for f in report["findings"])
    assert report["metadata"]["token_usage"]["total_tokens"] == 600
    assert report["metadata"]["token_budget"]["charged_tokens"] == 600
