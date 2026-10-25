import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.loop import AgentLoop
from app.agent.tools import AgentTools
from app.db.models import Chunk, Document
from app.ingest.pipeline import (
    DocumentMetadata,
    IngestionConfig,
    IngestionPipeline,
    create_ingestion_job,
)
from app.llm.base import LLMMessage, LLMResult, TokenUsage, ToolCall, ToolDefinition
from app.llm.fake import FakeLLM, FakeResponse
from app.rag.retriever import Retriever
from app.store.base import SearchFilters
from app.store.pgvector_store import PgVectorStore
from tests.helpers import FakeEmbedder


async def _add_document(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    filename: str,
    title: str,
    source_agency: str,
    doc_type: str,
    year: int,
) -> Document:
    document = Document(
        filename=filename,
        title=title,
        source_agency=source_agency,
        doc_type=doc_type,
        year=year,
        version="v1",
        content_sha256=(uuid4().hex + uuid4().hex)[:64],
        byte_size=10,
        page_count=None,
    )
    async with sessionmaker() as session:
        session.add(document)
        await session.commit()
        await session.refresh(document)
    return document


async def _ingest_text(
    sessionmaker: async_sessionmaker[AsyncSession],
    embedder: FakeEmbedder,
    config: IngestionConfig,
    tmp_path: Path,
) -> Chunk:
    path = tmp_path / "agent-source.txt"
    path.write_text(
        "Synthetic agent source content about training records and retention.",
        encoding="utf-8",
    )
    job_id = await create_ingestion_job(sessionmaker)
    pipeline = IngestionPipeline(sessionmaker, embedder, config)
    await pipeline.run_upload_job(
        job_id,
        path,
        DocumentMetadata(
            filename="agent-source.txt",
            title="Agent Source",
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


def _tools(
    sessionmaker: async_sessionmaker[AsyncSession],
    embedder: FakeEmbedder,
    *,
    max_output_chars: int = 8000,
) -> AgentTools:
    retriever = Retriever(
        embedder,
        {"pgvector": PgVectorStore(sessionmaker)},
        "pgvector",
    )
    return AgentTools(
        retriever,
        sessionmaker,
        max_output_chars=max_output_chars,
        max_metadata_rows=50,
    )


async def test_query_metadata_filters_sorts_and_limits(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
) -> None:
    await _add_document(
        sessionmaker,
        filename="old-guidance.pdf",
        title="Old Guidance",
        source_agency="FDA",
        doc_type="guidance",
        year=2010,
    )
    await _add_document(
        sessionmaker,
        filename="new-guidance.pdf",
        title="New Guidance",
        source_agency="FDA",
        doc_type="guidance",
        year=2024,
    )
    await _add_document(
        sessionmaker,
        filename="regulation.pdf",
        title="Regulation",
        source_agency="FDA",
        doc_type="regulation",
        year=2025,
    )
    await _add_document(
        sessionmaker,
        filename="other-agency.pdf",
        title="Other Agency",
        source_agency="OSHA",
        doc_type="guidance",
        year=2025,
    )

    tools = _tools(sessionmaker, fake_embedder)
    result = await tools.execute(
        "query_metadata",
        {
            "doc_type": "guidance",
            "year_min": 2015,
            "sort_by": "year",
            "sort_order": "desc",
            "limit": 1,
        },
        base_filters=SearchFilters(source_agency="FDA"),
        backend="pgvector",
    )

    assert result.error is None
    assert result.validated_arguments is not None
    assert result.validated_arguments["sort_by"] == "year"
    payload = json.loads(result.content)
    assert payload["count"] == 1
    assert payload["documents"][0]["filename"] == "new-guidance.pdf"
    assert payload["documents"][0]["year"] == 2024


async def test_query_metadata_rejects_invalid_arguments(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
) -> None:
    tools = _tools(sessionmaker, fake_embedder)
    result = await tools.execute(
        "query_metadata",
        {"sort_by": "year; drop table documents"},
        base_filters=SearchFilters(),
        backend="pgvector",
    )

    assert result.error == "invalid_arguments"
    payload = json.loads(result.content)
    assert payload["error"] == "invalid_arguments"
    assert "drop table" not in result.content


async def test_search_documents_returns_hits_and_truncates_output(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    chunk = await _ingest_text(sessionmaker, fake_embedder, ingestion_config, tmp_path)
    tools = _tools(sessionmaker, fake_embedder, max_output_chars=200)

    result = await tools.execute(
        "search_documents",
        {"query": chunk.text, "top_k": 1},
        base_filters=SearchFilters(source_agency="Synthetic Agency"),
        backend="pgvector",
    )

    assert result.error is None
    assert result.hits
    assert result.hits[0].chunk_id == chunk.id
    assert result.truncated is True
    assert "truncated" in result.summary
    assert str(chunk.id) in result.content

    no_match = await tools.execute(
        "search_documents",
        {"query": chunk.text, "top_k": 1},
        base_filters=SearchFilters(source_agency="Other Agency"),
        backend="pgvector",
    )
    assert no_match.hits == ()
    assert no_match.error is None


async def test_agent_runs_multiple_tools_and_validates_citations(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    chunk = await _ingest_text(sessionmaker, fake_embedder, ingestion_config, tmp_path)
    llm = FakeLLM(
        [
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        id="call-meta",
                        name="query_metadata",
                        arguments={"doc_type": "guidance"},
                    ),
                ),
                usage=TokenUsage(input_tokens=10, output_tokens=2),
            ),
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        id="call-search",
                        name="search_documents",
                        arguments={"query": chunk.text, "top_k": 1},
                    ),
                ),
                usage=TokenUsage(input_tokens=20, output_tokens=3),
            ),
            FakeResponse(
                text=json.dumps(
                    {
                        "answer": "Training records must be retained.",
                        "citations": [str(chunk.id)],
                    }
                ),
                usage=TokenUsage(input_tokens=30, output_tokens=4),
            ),
        ]
    )
    agent = AgentLoop(
        llm,
        _tools(sessionmaker, fake_embedder),
        max_steps=5,
        step_timeout_seconds=5,
        total_timeout_seconds=10,
    )

    result = await agent.run("What does the source say about training records?")

    assert result.partial is False
    assert result.step_count == 2
    assert [step.tool for step in result.trace] == ["query_metadata", "search_documents"]
    assert result.trace[1].arguments["query"] == chunk.text
    assert result.trace[1].arguments["top_k"] == 1
    assert result.grounded is True
    assert result.grounding_reason is None
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == chunk.id
    assert result.usage.total_tokens == 69
    assert result.latency_ms >= 0
    assert len(llm.requests) == 3
    tool_messages = llm.requests[2]["messages"]
    assert any(
        isinstance(message, LLMMessage)
        and message.role == "tool"
        and str(chunk.id) in message.content
        for message in tool_messages
    )


async def test_agent_step_limit_returns_partial_answer(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    chunk = await _ingest_text(sessionmaker, fake_embedder, ingestion_config, tmp_path)
    llm = FakeLLM(
        [
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        id="call-1",
                        name="search_documents",
                        arguments={"query": chunk.text},
                    ),
                )
            ),
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        id="call-2",
                        name="search_documents",
                        arguments={"query": chunk.text},
                    ),
                )
            ),
            FakeResponse(
                text=json.dumps(
                    {
                        "answer": "Partial answer: training records are retained.",
                        "citations": [str(chunk.id)],
                    }
                )
            ),
        ]
    )
    agent = AgentLoop(
        llm,
        _tools(sessionmaker, fake_embedder),
        max_steps=2,
        step_timeout_seconds=5,
        total_timeout_seconds=10,
    )

    result = await agent.run("Find the retention rule.")

    assert result.partial is True
    assert result.partial_reason == "step_limit"
    assert result.step_count == 2
    assert len(result.trace) == 2
    assert result.grounded is True
    assert result.citations[0].chunk_id == chunk.id
    assert result.answer.startswith("Partial answer")
    assert len(llm.requests) == 3
    assert llm.requests[2]["tools"] == []


def test_agent_max_steps_is_hard_capped_by_settings() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(AGENT_MAX_STEPS=6)


async def test_agent_model_timeout_returns_partial_result(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
) -> None:
    class SlowLLM:
        async def chat(
            self,
            messages: list[LLMMessage],
            *,
            tools: list[ToolDefinition] | tuple[ToolDefinition, ...] = (),
            temperature: float = 0.0,
            max_tokens: int = 1024,
        ) -> LLMResult:
            import asyncio

            await asyncio.sleep(0.1)
            return LLMResult(text="late")

        async def close(self) -> None:
            return None

    agent = AgentLoop(
        SlowLLM(),  # type: ignore[arg-type]
        _tools(sessionmaker, fake_embedder),
        max_steps=2,
        step_timeout_seconds=0.01,
        total_timeout_seconds=0.05,
    )

    result = await agent.run("Will this time out?")

    assert result.partial is True
    assert result.partial_reason == "timeout"
    assert result.step_count == 0
    assert result.trace == ()
    assert "step or time limit" in result.answer
