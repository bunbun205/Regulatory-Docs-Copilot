from uuid import uuid4

import pytest

from app.gapcheck.judge import ClauseJudgement, GapCheckJudge, RequirementJudgement
from app.gapcheck.requirements import Requirement
from app.gapcheck.runner import (
    GapCheckCancelled,
    GapCheckConfig,
    GapCheckRunner,
)
from app.llm.base import TokenUsage
from app.llm.fake import FakeLLM
from app.rag.retriever import RetrievalResult
from app.store.base import SearchFilters, SearchHit
from tests.helpers import FakeEmbedder


def _hit(text: str, *, score: float = 0.9, document_id=None) -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=document_id or uuid4(),
        chunk_index=0,
        text=text,
        score=score,
        page=2,
        section_heading="Records",
        filename="records.pdf",
        title="Records Regulation",
        source_agency="FDA",
        doc_type="regulation",
        year=2024,
        version="v1",
    )


class StubRetriever:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        filters: SearchFilters | None = None,
        backend: str | None = None,
    ) -> RetrievalResult:
        self.queries.append(query)
        return RetrievalResult(hits=tuple(self.hits), backend="pgvector", latency_ms=0.0)


class StubJudge:
    def __init__(self) -> None:
        self.clause_calls = 0
        self.requirement_calls = 0

    async def judge_clause(
        self,
        *,
        clause_id: str,
        clause_text: str,
        section: str,
        retrieved_hits: list[SearchHit],
    ) -> ClauseJudgement:
        self.clause_calls += 1
        verdict = "conflict" if "destroyed" in clause_text else "compliant"
        return ClauseJudgement(
            verdict=verdict,
            citations=(str(retrieved_hits[0].chunk_id),),
            rationale="Stub judgement.",
            usage=TokenUsage(input_tokens=10, output_tokens=2),
        )

    async def judge_requirement(
        self,
        *,
        requirement: Requirement,
        candidate_clauses: list[dict[str, str]],
    ) -> RequirementJudgement:
        self.requirement_calls += 1
        if "retained" in requirement.text:
            return RequirementJudgement(
                verdict="missing",
                citations=(),
                rationale="No SOP clause retains records.",
                usage=TokenUsage(input_tokens=5, output_tokens=1),
            )
        return RequirementJudgement(
            verdict="addressed",
            citations=("SOP-002",),
            rationale="Training is addressed.",
            usage=TokenUsage(input_tokens=5, output_tokens=1),
        )


SOP_TEXT = """# Records
1. Records are destroyed after one year.

# Training
2. Training is provided to all staff.
"""


def _runner(
    retriever: StubRetriever,
    judge: StubJudge,
    *,
    config: GapCheckConfig | None = None,
    progress=None,
    cancel_check=None,
) -> GapCheckRunner:
    return GapCheckRunner(
        retriever,  # type: ignore[arg-type]
        FakeEmbedder(),
        judge,  # type: ignore[arg-type]
        config
        or GapCheckConfig(
            max_clauses=10,
            max_requirements=10,
            relevance_threshold=0.5,
            judge_concurrency=2,
            retrieval_concurrency=2,
        ),
        job_id=str(uuid4()),
        model_label="fake:fake",
        progress_callback=progress,
        cancel_check=cancel_check,
    )


async def test_runner_checks_both_directions_and_validates_citations() -> None:
    hit = _hit("Records shall be retained for five years. Staff shall complete annual training.")
    retriever = StubRetriever([hit])
    judge = StubJudge()
    updates: list[dict[str, object]] = []

    async def progress(update: dict[str, object]) -> None:
        updates.append(update)

    report = await _runner(retriever, judge, progress=progress).run(SOP_TEXT)

    findings = report["findings"]
    assert [finding["direction"] for finding in findings] == [
        "sop_to_regulation",
        "sop_to_regulation",
        "regulation_to_sop",
        "regulation_to_sop",
    ]
    assert [finding["verdict"] for finding in findings] == [
        "conflict",
        "compliant",
        "missing",
        "addressed",
    ]
    assert findings[0]["severity"] == "high"
    assert findings[2]["severity"] == "high"
    assert findings[3]["severity"] == "low"
    assert findings[0]["sop_clause_refs"] == ["SOP-001"]
    assert findings[3]["sop_clause_refs"] == ["SOP-002"]
    assert findings[0]["regulation_citations"][0]["chunk_id"] == str(hit.chunk_id)
    assert findings[2]["regulation_citations"][0]["chunk_id"] == str(hit.chunk_id)
    assert report["counts_by_verdict"]["conflict"] == 1
    assert report["counts_by_verdict"]["missing"] == 1
    assert report["counts_by_direction"] == {
        "sop_to_regulation": 2,
        "regulation_to_sop": 2,
    }
    assert report["metadata"]["token_usage"]["total_tokens"] == 36
    assert {update["phase"] for update in updates} >= {
        "clauses",
        "requirements",
        "finalizing",
    }


async def test_runner_skips_llm_for_weak_retrieval() -> None:
    retriever = StubRetriever([_hit("Weakly related text.", score=0.1)])
    judge = StubJudge()

    report = await _runner(
        retriever,
        judge,
        config=GapCheckConfig(
            max_clauses=10,
            relevance_threshold=0.5,
            judge_concurrency=2,
            retrieval_concurrency=2,
        ),
    ).run(SOP_TEXT)

    assert judge.clause_calls == 0
    assert judge.requirement_calls == 0
    assert {finding["verdict"] for finding in report["findings"]} == {"not_covered_by_corpus"}


async def test_runner_reports_requirement_cap() -> None:
    text = " ".join(f"Control {index} shall be documented." for index in range(5))
    retriever = StubRetriever([_hit(text)])
    judge = StubJudge()

    report = await _runner(
        retriever,
        judge,
        config=GapCheckConfig(
            max_clauses=10,
            max_requirements=2,
            relevance_threshold=0.5,
            judge_concurrency=2,
            retrieval_concurrency=2,
        ),
    ).run(SOP_TEXT)

    assert "requirements" in report["caps_hit"]
    assert report["metadata"]["requirements_total"] == 2
    assert report["metadata"]["caps"]["requirements_capped"] is True


async def test_runner_stops_on_cancellation() -> None:
    async def cancel_check() -> bool:
        return True

    with pytest.raises(GapCheckCancelled):
        await _runner(
            StubRetriever([_hit("Records shall be retained.")]),
            StubJudge(),
            cancel_check=cancel_check,
        ).run(SOP_TEXT)


async def test_runner_marks_judge_failed_when_token_cap_is_reached() -> None:
    llm = FakeLLM()

    report = await _runner(
        StubRetriever([_hit("Records shall be retained for five years.")]),
        GapCheckJudge(llm),
        config=GapCheckConfig(
            max_clauses=10,
            max_tokens=50,
            relevance_threshold=0.5,
            judge_concurrency=1,
            retrieval_concurrency=1,
        ),
    ).run(SOP_TEXT)

    verdicts = [finding["verdict"] for finding in report["findings"]]
    assert "tokens" in report["caps_hit"]
    assert set(verdicts) == {"judge_failed"}
    assert not llm.requests
    assert report["metadata"]["token_usage"]["total_tokens"] == 0
    assert report["metadata"]["caps"]["max_tokens"] == 50


class ScopeAwareRetriever(StubRetriever):
    def __init__(self, clause_hits: list[SearchHit], global_hits: list[SearchHit]) -> None:
        super().__init__(clause_hits)
        self.global_hits = global_hits

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        filters: SearchFilters | None = None,
        backend: str | None = None,
    ) -> RetrievalResult:
        self.queries.append(query)
        hits = self.global_hits if "\n" in query else self.hits
        return RetrievalResult(hits=tuple(hits), backend="pgvector", latency_ms=0.0)


async def test_runner_filters_requirement_chunks_to_globally_relevant_documents() -> None:
    document_a = uuid4()
    document_b = uuid4()
    hit_a = _hit(
        "The laboratory shall retain records for five years.",
        document_id=document_a,
    )
    hit_b = _hit(
        "The laboratory shall train all staff annually.",
        document_id=document_b,
    )
    retriever = ScopeAwareRetriever([hit_a, hit_b], [hit_a])

    report = await _runner(
        retriever,
        StubJudge(),
        config=GapCheckConfig(
            max_clauses=10,
            max_requirements=10,
            relevance_threshold=0.5,
            global_top_documents=1,
            judge_concurrency=2,
            retrieval_concurrency=2,
        ),
    ).run(SOP_TEXT)

    assert report["metadata"]["requirements_total"] == 1
    assert report["metadata"]["requirement_document_ids"] == [str(document_a)]
    assert all(
        citation["document_id"] == str(document_a)
        for finding in report["findings"]
        for citation in finding["regulation_citations"]
    )
