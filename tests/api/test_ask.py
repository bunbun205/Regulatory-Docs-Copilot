import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import Scope
from app.db.models import Chunk
from app.llm.base import LLMError, LLMMessage, LLMResult, TokenUsage, ToolDefinition
from app.llm.fake import FakeLLM, FakeResponse


async def _upload(
    client: AsyncClient,
    key: str,
    *,
    content: bytes,
    filename: str = "ask-source.txt",
) -> str:
    response = await client.post(
        "/v1/documents",
        headers={"X-API-Key": key},
        files={"file": (filename, content, "text/plain")},
        data={
            "title": "Ask Source",
            "source_agency": "Synthetic Agency",
            "doc_type": "guidance",
            "year": "2026",
            "version": "v1",
        },
    )
    assert response.status_code == 202, response.text
    return str(response.json()["job_id"])


async def _wait_for_job(client: AsyncClient, key: str, job_id: str) -> dict[str, Any]:
    for _ in range(500):
        response = await client.get(f"/v1/jobs/{job_id}", headers={"X-API-Key": key})
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        await asyncio.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not finish in time.")


async def _ingest_one(
    client: AsyncClient,
    writer: str,
    reader: str,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Chunk:
    job_id = await _upload(
        client,
        writer,
        content=b"Synthetic ask route content about training records.",
    )
    job = await _wait_for_job(client, reader, job_id)
    assert job["status"] == "completed"
    async with sessionmaker() as session:
        chunk = await session.scalar(select(Chunk).order_by(Chunk.chunk_index))
    assert chunk is not None
    return chunk


async def test_ask_returns_grounded_answer_with_validated_citation(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    writer = await make_api_key(name="ask-writer", scope=Scope.WRITE)
    reader = await make_api_key(name="ask-reader", scope=Scope.READ)
    chunk = await _ingest_one(client, writer, reader, sessionmaker)

    app.state.llm_client = FakeLLM(
        [
            FakeResponse(
                text=json.dumps(
                    {
                        "answer": "Training records must be kept.",
                        "citations": [str(chunk.id)],
                    }
                ),
                usage=TokenUsage(input_tokens=25, output_tokens=8),
            )
        ]
    )
    response = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": chunk.text, "top_k": 3},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["grounding_reason"] is None
    assert payload["insufficient_evidence"] is False
    assert payload["answer"] == "Training records must be kept."
    assert len(payload["citations"]) == 1
    citation = payload["citations"][0]
    assert citation["chunk_id"] == str(chunk.id)
    assert citation["title"] == "Ask Source"
    assert citation["page"] is None
    assert citation["snippet"] == chunk.text
    assert citation["score"] == pytest.approx(1.0, abs=1e-5)
    assert payload["top_score"] == pytest.approx(1.0, abs=1e-5)
    assert payload["usage"] == {
        "input_tokens": 25,
        "output_tokens": 8,
        "total_tokens": 33,
    }
    assert payload["latency_ms"]["retrieve_ms"] >= 0
    assert payload["latency_ms"]["generate_ms"] == 0.0
    fake = app.state.llm_client
    assert isinstance(fake, FakeLLM)
    prompt = fake.requests[0]["messages"][1]
    assert isinstance(prompt, LLMMessage)
    assert str(chunk.id) in prompt.content
    assert chunk.text in prompt.content


async def test_ask_strips_invented_citation_and_flags_ungrounded(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    writer = await make_api_key(name="ask-bad-writer", scope=Scope.WRITE)
    reader = await make_api_key(name="ask-bad-reader", scope=Scope.READ)
    chunk = await _ingest_one(client, writer, reader, sessionmaker)

    app.state.llm_client = FakeLLM(
        [FakeResponse(text=json.dumps({"answer": "Invented answer.", "citations": [str(uuid4())]}))]
    )
    response = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": chunk.text},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is False
    assert payload["grounding_reason"] == "no_valid_citations"
    assert payload["citations"] == []


async def test_ask_abstains_without_calling_llm_when_below_threshold(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = await make_api_key(name="ask-abstain-writer", scope=Scope.WRITE)
    reader = await make_api_key(name="ask-abstain-reader", scope=Scope.READ)
    await _ingest_one(client, writer, reader, sessionmaker)

    fake = FakeLLM()
    app.state.llm_client = fake
    monkeypatch.setattr("app.api.routes.ask.settings.ABSTENTION_THRESHOLD", 1.01)
    response = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": "A completely unrelated question about spacecraft."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["insufficient_evidence"] is True
    assert payload["grounded"] is False
    assert payload["grounding_reason"] == "below_threshold"
    assert payload["citations"] == []
    assert payload["usage"]["total_tokens"] == 0
    assert fake.requests == []


async def test_ask_maps_llm_failure_to_502(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    writer = await make_api_key(name="ask-fail-writer", scope=Scope.WRITE)
    reader = await make_api_key(name="ask-fail-reader", scope=Scope.READ)
    chunk = await _ingest_one(client, writer, reader, sessionmaker)

    class FailingLLM:
        async def chat(
            self,
            messages: Sequence[LLMMessage],
            *,
            tools: Sequence[ToolDefinition] = (),
            temperature: float = 0.0,
            max_tokens: int = 1024,
        ) -> LLMResult:
            raise LLMError("provider detail must not leak")

        async def close(self) -> None:
            return None

    app.state.llm_client = FailingLLM()
    response = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": chunk.text},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_unavailable"
    assert "provider detail" not in response.text


async def test_ask_validates_auth_query_and_backend(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    reader = await make_api_key(name="ask-validation-reader", scope=Scope.READ)

    missing = await client.post("/v1/ask", json={"query": "hello"})
    assert missing.status_code == 401

    blank = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": "   "},
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "validation_error"

    too_many = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": "hello", "top_k": 51},
    )
    assert too_many.status_code == 422

    unavailable = await client.post(
        "/v1/ask",
        headers={"X-API-Key": reader},
        json={"query": "hello", "backend": "qdrant"},
    )
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["code"] == "backend_unavailable"
