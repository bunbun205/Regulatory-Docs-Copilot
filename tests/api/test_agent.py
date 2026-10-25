import json
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import Scope
from app.db.models import Chunk
from app.ingest.pipeline import (
    DocumentMetadata,
    IngestionConfig,
    IngestionPipeline,
    create_ingestion_job,
)
from app.llm.base import LLMError, LLMMessage, LLMResult, TokenUsage, ToolCall, ToolDefinition
from app.llm.fake import FakeLLM, FakeResponse
from tests.helpers import FakeEmbedder


async def _ingest_source(
    sessionmaker: async_sessionmaker[AsyncSession],
    embedder: FakeEmbedder,
    config: IngestionConfig,
    tmp_path: Path,
) -> Chunk:
    path = tmp_path / "agent-api-source.txt"
    path.write_text(
        "Synthetic agent API source content about training records.",
        encoding="utf-8",
    )
    job_id = await create_ingestion_job(sessionmaker)
    pipeline = IngestionPipeline(sessionmaker, embedder, config)
    await pipeline.run_upload_job(
        job_id,
        path,
        DocumentMetadata(
            filename="agent-api-source.txt",
            title="Agent API Source",
            source_agency="Synthetic Agency",
            doc_type="guidance",
            year=2026,
            version="v1",
        ),
    )
    async with sessionmaker() as session:
        chunk = await session.scalar(select(Chunk).order_by(Chunk.chunk_index))
    assert chunk is not None
    return chunk


async def test_agent_endpoint_returns_trace_and_citations(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    reader = await make_api_key(name="agent-reader", scope=Scope.READ)
    chunk = await _ingest_source(sessionmaker, fake_embedder, ingestion_config, tmp_path)
    app.state.llm_client = FakeLLM(
        [
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        id="meta-1",
                        name="query_metadata",
                        arguments={"doc_type": "guidance"},
                    ),
                ),
                usage=TokenUsage(input_tokens=5, output_tokens=1),
            ),
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        id="search-1",
                        name="search_documents",
                        arguments={"query": chunk.text, "top_k": 1},
                    ),
                ),
                usage=TokenUsage(input_tokens=6, output_tokens=2),
            ),
            FakeResponse(
                text=json.dumps(
                    {
                        "answer": "Training records are covered.",
                        "citations": [str(chunk.id)],
                    }
                ),
                usage=TokenUsage(input_tokens=7, output_tokens=3),
            ),
        ]
    )

    response = await client.post(
        "/v1/agent/run",
        headers={"X-API-Key": reader},
        json={
            "query": "What does the source say about training records?",
            "filters": {"source_agency": "Synthetic Agency", "doc_type": "guidance"},
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["query"] == "What does the source say about training records?"
    assert payload["backend"] == "pgvector"
    assert payload["answer"] == "Training records are covered."
    assert payload["grounded"] is True
    assert payload["grounding_reason"] is None
    assert payload["step_count"] == 2
    assert payload["partial"] is False
    assert payload["partial_reason"] is None
    assert [step["tool"] for step in payload["trace"]] == [
        "query_metadata",
        "search_documents",
    ]
    assert payload["trace"][1]["arguments"]["query"] == chunk.text
    assert payload["trace"][1]["arguments"]["top_k"] == 1
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["chunk_id"] == str(chunk.id)
    assert payload["citations"][0]["snippet"] == chunk.text
    assert payload["usage"] == {
        "input_tokens": 18,
        "output_tokens": 6,
        "total_tokens": 24,
    }
    assert payload["latency_ms"] >= 0


async def test_agent_endpoint_validates_auth_query_and_backend(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    reader = await make_api_key(name="agent-validation-reader", scope=Scope.READ)

    missing = await client.post("/v1/agent/run", json={"query": "hello"})
    assert missing.status_code == 401

    blank = await client.post(
        "/v1/agent/run",
        headers={"X-API-Key": reader},
        json={"query": "   "},
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "validation_error"

    unavailable = await client.post(
        "/v1/agent/run",
        headers={"X-API-Key": reader},
        json={"query": "hello", "backend": "qdrant"},
    )
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["code"] == "backend_unavailable"


async def test_agent_endpoint_maps_llm_failure_to_502(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    reader = await make_api_key(name="agent-failure-reader", scope=Scope.READ)

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
        "/v1/agent/run",
        headers={"X-API-Key": reader},
        json={"query": "hello"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_unavailable"
    assert "provider detail" not in response.text
