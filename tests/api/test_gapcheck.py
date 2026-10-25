import json
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.security import Scope
from app.db.models import ApiKey, Chunk, GapCheckJob
from app.ingest.pipeline import (
    DocumentMetadata,
    IngestionConfig,
    IngestionPipeline,
    create_ingestion_job,
)
from app.llm.base import LLMMessage, LLMResult, TokenUsage, ToolDefinition
from tests.helpers import FakeEmbedder

SOP_TEXT = """# Records
1. Records are destroyed after one year.

# Training
2. Training is provided to all staff.
"""

REGULATION_TEXT = "Records shall be retained for five years. Staff shall complete annual training."


class ScriptedJudgeLLM:
    def __init__(self, chunk_id) -> None:  # type: ignore[no-untyped-def]
        self.chunk_id = str(chunk_id)
        self.requests = 0

    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        self.requests += 1
        user = messages[-1].content
        if "<regulation_requirement" in user:
            if "retained" in user:
                payload = {
                    "verdict": "missing",
                    "citations": [],
                    "rationale": "No SOP clause retains records.",
                }
            else:
                payload = {
                    "verdict": "addressed",
                    "citations": ["SOP-002"],
                    "rationale": "SOP-002 covers training.",
                }
        elif "<sop_clause id=" in user:
            verdict = "conflict" if "destroyed" in user else "compliant"
            payload = {
                "verdict": verdict,
                "citations": [self.chunk_id],
                "rationale": "The regulation is cited directly.",
            }
        else:
            payload = {
                "verdict": "missing",
                "citations": [],
                "rationale": "No judgement was requested.",
            }
        return LLMResult(
            text=json.dumps(payload),
            usage=TokenUsage(input_tokens=10, output_tokens=2),
        )

    async def close(self) -> None:
        return None


async def _ingest_regulation(
    sessionmaker: async_sessionmaker[AsyncSession],
    embedder: FakeEmbedder,
    config: IngestionConfig,
    tmp_path: Path,
) -> Chunk:
    path = tmp_path / "gapcheck-regulation.txt"
    path.write_text(REGULATION_TEXT, encoding="utf-8")
    job_id = await create_ingestion_job(sessionmaker)
    pipeline = IngestionPipeline(sessionmaker, embedder, config)
    await pipeline.run_upload_job(
        job_id,
        path,
        DocumentMetadata(
            filename="gapcheck-regulation.txt",
            title="Records Regulation",
            source_agency="FDA",
            doc_type="regulation",
            year=2024,
            version="v1",
        ),
    )
    async with sessionmaker() as session:
        chunk = await session.scalar(select(Chunk).order_by(Chunk.chunk_index))
    assert chunk is not None
    return chunk


async def test_gapcheck_endpoint_runs_both_directions_and_returns_valid_citations(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "GAPCHECK_RELEVANCE_THRESHOLD", 0.0)
    monkeypatch.setattr(settings, "GAPCHECK_JUDGE_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "GAPCHECK_RETRIEVAL_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "GAPCHECK_RETRIEVAL_TOP_K", 2)
    monkeypatch.setattr(settings, "GAPCHECK_MAX_REQUIREMENTS", 10)
    reader = await make_api_key(name="gapcheck-reader", scope=Scope.READ)
    chunk = await _ingest_regulation(sessionmaker, fake_embedder, ingestion_config, tmp_path)
    llm = ScriptedJudgeLLM(chunk.id)
    app.state.llm_client = llm

    response = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": reader},
        data={"text": SOP_TEXT, "doc_type": "regulation"},
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    poll = await client.get(f"/v1/gapcheck/{job_id}", headers={"X-API-Key": reader})
    assert poll.status_code == 200, poll.text
    payload = poll.json()
    assert payload["status"] == "completed"
    assert payload["progress"]["phase"] == "completed"
    assert payload["error"] is None
    report = payload["report"]
    assert report["banner"].startswith("Decision support only")
    assert len(report["sop_clauses"]) == 2
    assert report["counts_by_direction"] == {
        "sop_to_regulation": 2,
        "regulation_to_sop": 2,
    }
    assert [finding["verdict"] for finding in report["findings"]] == [
        "conflict",
        "compliant",
        "missing",
        "addressed",
    ]
    assert report["findings"][0]["severity"] == "high"
    assert report["findings"][2]["severity"] == "high"
    for finding in report["findings"]:
        for citation in finding["regulation_citations"]:
            assert citation["chunk_id"] == str(chunk.id)
    assert llm.requests == 4


async def test_gapcheck_accepts_file_and_rejects_other_key(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "GAPCHECK_RELEVANCE_THRESHOLD", 0.0)
    monkeypatch.setattr(settings, "GAPCHECK_JUDGE_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "GAPCHECK_RETRIEVAL_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "GAPCHECK_RETRIEVAL_TOP_K", 1)
    owner = await make_api_key(name="gapcheck-file-owner", scope=Scope.READ)
    other = await make_api_key(name="gapcheck-file-other", scope=Scope.READ)
    chunk = await _ingest_regulation(sessionmaker, fake_embedder, ingestion_config, tmp_path)
    app.state.llm_client = ScriptedJudgeLLM(chunk.id)

    response = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": owner},
        files={"file": ("sop.md", SOP_TEXT.encode("utf-8"), "text/markdown")},
        data={"doc_type": "regulation"},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    hidden = await client.get(f"/v1/gapcheck/{job_id}", headers={"X-API-Key": other})
    assert hidden.status_code == 404
    visible = await client.get(f"/v1/gapcheck/{job_id}", headers={"X-API-Key": owner})
    assert visible.status_code == 200
    assert visible.json()["status"] == "completed"


async def test_gapcheck_validates_inputs_and_auth(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "GAPCHECK_MAX_CLAUSES", 5)
    reader = await make_api_key(name="gapcheck-validation", scope=Scope.READ)

    missing_auth = await client.post("/v1/gapcheck", data={"text": SOP_TEXT})
    assert missing_auth.status_code == 401

    neither = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": reader},
        data={},
    )
    assert neither.status_code == 422
    assert neither.json()["error"]["code"] == "validation_error"

    both = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": reader},
        data={"text": SOP_TEXT},
        files={"file": ("sop.txt", SOP_TEXT.encode(), "text/plain")},
    )
    assert both.status_code == 422

    too_many = "\n\n".join(f"Paragraph {index} describes a distinct control." for index in range(6))
    capped = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": reader},
        data={"text": too_many},
    )
    assert capped.status_code == 422
    assert capped.json()["error"]["code"] == "clause_cap_exceeded"

    unavailable = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": reader},
        data={"text": SOP_TEXT, "backend": "qdrant"},
    )
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["code"] == "backend_unavailable"

    unknown = await client.get(
        "/v1/gapcheck/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": reader},
    )
    assert unknown.status_code == 404


async def test_gapcheck_enforces_per_key_active_job_limit(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    reader = await make_api_key(name="gapcheck-limit", scope=Scope.READ)
    async with sessionmaker() as session:
        key = await session.scalar(select(ApiKey).where(ApiKey.name == "gapcheck-limit"))
        assert key is not None
        session.add(
            GapCheckJob(
                api_key_id=key.id,
                status="queued",
                progress={"phase": "queued"},
            )
        )
        await session.commit()

    response = await client.post(
        "/v1/gapcheck",
        headers={"X-API-Key": reader},
        data={"text": SOP_TEXT},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "gapcheck_limit"
    assert response.headers["Retry-After"] == "30"


async def test_gapcheck_cancel_sets_cooperative_flag_and_is_key_scoped(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await make_api_key(name="gapcheck-cancel-owner", scope=Scope.READ)
    other = await make_api_key(name="gapcheck-cancel-other", scope=Scope.READ)
    async with sessionmaker() as session:
        key = await session.scalar(select(ApiKey).where(ApiKey.name == "gapcheck-cancel-owner"))
        assert key is not None
        job = GapCheckJob(
            api_key_id=key.id,
            status="queued",
            progress={"phase": "queued"},
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    denied = await client.post(
        f"/v1/gapcheck/{job_id}/cancel",
        headers={"X-API-Key": other},
    )
    assert denied.status_code == 404

    response = await client.post(
        f"/v1/gapcheck/{job_id}/cancel",
        headers={"X-API-Key": owner},
    )
    assert response.status_code == 202
    assert response.json()["cancel_requested"] is True
    async with sessionmaker() as session:
        stored = await session.get(GapCheckJob, job_id)
    assert stored is not None
    assert stored.cancel_requested is True
