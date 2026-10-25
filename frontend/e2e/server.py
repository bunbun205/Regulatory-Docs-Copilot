"""Isolated browser-test entrypoint. Never import this from production app code.

Run with uvicorn frontend.e2e.server:app. It resets only its dedicated _test DB
and collection. Fixed test credentials are confined to those isolated stores.
"""

# ruff: noqa: E402
import asyncio
import hashlib
import json
import os
import re
from collections.abc import Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from tempfile import TemporaryDirectory
from uuid import UUID

import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get(
    "FRONTEND_E2E_DATABASE_URL",
    "postgresql+asyncpg://labdocs:labdocs@127.0.0.1:5432/labdocs_frontend_test",
)
database_name = make_url(DATABASE_URL).database or ""
if not re.fullmatch(r"labdocs_frontend[\w]*_test", database_name):
    raise RuntimeError("Browser tests require a dedicated labdocs_frontend*_test database.")
COLLECTION = "labdocs_frontend_test"
os.environ.update(
    LABDOCS_ENVIRONMENT="testing",
    LABDOCS_DATABASE_URL=DATABASE_URL,
    LABDOCS_VECTOR_BACKEND="both",
    LABDOCS_QDRANT_COLLECTION=COLLECTION,
    LABDOCS_LLM_PROVIDER="fake",
    LABDOCS_LLM_MODEL="frontend-fixture",
)

from app.core.security import hash_api_key
from app.db.base import Base
from app.db.models import ApiKey, GapCheckJob
from app.gapcheck.report import ALL_VERDICTS, RegulationCitation, build_report, make_finding
from app.llm.base import LLMMessage, LLMResult, TokenUsage, ToolCall, ToolDefinition
from app.llm.fake import FakeLLM, FakeResponse
from app.main import create_app
from app.store.base import VectorRecord
from tests.helpers import FakeEmbedder

WRITE_KEY = "frontend-e2e-write"
READ_KEY = "frontend-e2e-read"
WRITER_ID = UUID("10000000-0000-4000-8000-000000000001")
REPORT_JOB_ID = UUID("10000000-0000-4000-8000-000000000006")
JOB_ID = UUID("10000000-0000-4000-8000-000000000003")
CHUNK_ID = UUID("10000000-0000-4000-8000-000000000004")
SOURCE = "Staff must record instrument checks in a training log before using the equipment."


class BrowserLLM(FakeLLM):
    """Per-request scripts live only in this isolated browser entrypoint."""

    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        if not tools:
            if messages and messages[0].content.startswith(
                "You are a regulatory compliance judge."
            ):
                # Bounded delay makes the real asynchronous job's progress/cancel states observable.
                await asyncio.sleep(1.5)
                quoted = "\n".join(
                    message.content for message in messages if message.role == "user"
                )
                clause_check = "<sop_clause " in quoted
                ids = re.findall(
                    r"chunk_id=([0-9a-f-]{36})" if clause_check else r"clause_id=(SOP-\d+)",
                    quoted,
                )
                response = FakeResponse(
                    text=json.dumps(
                        {
                            "verdict": "compliant" if clause_check else "addressed",
                            "citations": list(dict.fromkeys(ids)),
                            "rationale": (
                                "Synthetic browser fixture: the provided training-log text "
                                "matches the seeded requirement."
                            ),
                        }
                    ),
                    usage=TokenUsage(input_tokens=24, output_tokens=8),
                )
                return await FakeLLM([response]).chat(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
            quoted = "\n".join(message.content for message in messages if message.role == "user")
            ids = re.findall(r"chunk_id=([0-9a-f-]{36})", quoted)
            response = FakeResponse(
                text=json.dumps(
                    {
                        "answer": "Record instrument checks before using equipment. [1]",
                        "citations": list(dict.fromkeys(ids))[:1],
                    }
                ),
                usage=TokenUsage(input_tokens=24, output_tokens=8),
            )
            return await FakeLLM([response]).chat(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        completed = [message for message in messages if message.role == "tool"]
        if not completed:
            response = FakeResponse(
                tool_calls=(ToolCall("browser-metadata", "query_metadata", {"limit": 5}),)
            )
        elif not any(message.name == "search_documents" for message in completed):
            response = FakeResponse(
                tool_calls=(
                    ToolCall("browser-search", "search_documents", {"query": SOURCE, "top_k": 2}),
                )
            )
        else:
            payload = json.loads(completed[-1].content)
            ids = [row["chunk_id"] for row in payload.get("results", [])]
            response = FakeResponse(
                text=json.dumps(
                    {
                        "answer": "Record instrument checks before using equipment. [1]",
                        "citations": ids,
                    }
                ),
                usage=TokenUsage(input_tokens=24, output_tokens=8),
            )
        return await FakeLLM([response]).chat(
            messages, tools=tools, temperature=temperature, max_tokens=max_tokens
        )


async def prepare_database() -> None:
    admin_url = make_url(DATABASE_URL).set(drivername="postgresql", database="postgres")
    admin = await asyncpg.connect(admin_url.render_as_string(hide_password=False))
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", database_name):
            await admin.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin.close()
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def seed(application) -> None:
    embedder = FakeEmbedder()
    application.state.embedder = embedder
    await application.state.llm_client.close()
    # Browser scripts never enter the production provider factory.
    application.state.llm_client = BrowserLLM(
        default_text=json.dumps(
            {
                "answer": "Record instrument checks before using equipment. [1]",
                "citations": [str(CHUNK_ID)],
            }
        )
    )
    record = VectorRecord(
        chunk_id=CHUNK_ID,
        document_id=UUID("10000000-0000-4000-8000-000000000005"),
        chunk_index=0,
        text=SOURCE,
        token_count=15,
        page=1,
        section_heading="Training",
        embedding=tuple(float(value) for value in embedder.embed([SOURCE])[0]),
        filename="synthetic-browser-fixture.txt",
        title="Instrument checks — synthetic browser fixture",
        source_agency="Synthetic test source",
        doc_type="training",
        year=2026,
        version="Test fixture v1",
        content_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
        byte_size=len(SOURCE.encode()),
        page_count=1,
    )
    for store in application.state.vector_stores.values():
        if store.name == "qdrant":
            await store.delete_collection()
            await store.ensure_ready()
        await store.upsert([record])
    if os.environ.get("FRONTEND_E2E_LARGE_CORPUS") == "1":
        # Test-entrypoint-only dataset. Never touches the native corpus or a
        # production provider. Batch both stores to exercise real list/count SQL.
        for start in range(0, 5000, 100):
            batch = []
            for index in range(start, start + 100):
                for chunk in range(2):
                    batch.append(
                        VectorRecord(
                            chunk_id=UUID(int=10_000_000 + index * 2 + chunk),
                            document_id=UUID(int=20_000_000 + index),
                            chunk_index=chunk,
                            text=f"Synthetic performance document {index}, chunk {chunk}.",
                            token_count=12,
                            page=chunk + 1,
                            section_heading="Synthetic performance fixture",
                            embedding=tuple(
                                float(value)
                                for value in embedder.embed(
                                    [f"Synthetic performance document {index}, chunk {chunk}."]
                                )[0]
                            ),
                            filename=f"performance-{index:05}.txt",
                            title=f"Synthetic performance document {index:05}",
                            source_agency="Performance target"
                            if index % 100 == 0
                            else "Performance corpus",
                            doc_type="guidance",
                            year=2020 + index % 6,
                            version="Synthetic performance v1",
                            content_sha256=hashlib.sha256(
                                f"performance-{index}".encode()
                            ).hexdigest(),
                            byte_size=100,
                            page_count=2,
                        )
                    )
            for store in application.state.vector_stores.values():
                await store.upsert(batch)
    if os.environ.get("FRONTEND_E2E_LARGE_CORPUS") == "1":
        from pathlib import Path

        counts = {
            name: await store.count() for name, store in application.state.vector_stores.items()
        }
        if any(count != 10001 for count in counts.values()):
            raise RuntimeError("The isolated performance corpus did not finish seeding.")
        manifest = Path("../docs/verification/frontend-f6/performance-corpus.json")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {"synthetic": True, "documents": 5001, "actual_store_counts": counts}, indent=2
            )
            + "\n"
        )
    now = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    async with application.state.sessionmaker() as session:
        session.add_all(
            [
                ApiKey(
                    id=WRITER_ID,
                    name="frontend-review",
                    key_hash=hash_api_key(WRITE_KEY),
                    scope="write",
                ),
                ApiKey(name="read-only-review", key_hash=hash_api_key(READ_KEY), scope="read"),
            ]
        )
        await session.flush()
        session.add(
            GapCheckJob(
                id=JOB_ID,
                api_key_id=WRITER_ID,
                status="completed",
                progress={
                    "phase": "completed",
                    "clauses_total": 1,
                    "clauses_done": 1,
                    "requirements_total": 0,
                    "requirements_done": 0,
                },
                report=build_report(
                    job_id=str(JOB_ID),
                    sop_clauses=[],
                    findings=[],
                    metadata={"model": "fake:frontend-fixture", "backend": "pgvector"},
                    caps_hit=[],
                    generated_at=now,
                ),
                created_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        # A labelled report fixture covers every verdict treatment. It is not a model run.
        fixture_citation = RegulationCitation(
            chunk_id=str(CHUNK_ID),
            document_id=str(record.document_id),
            title=record.title,
            page=1,
            snippet=SOURCE,
            score=0.82,
        )
        clauses = [
            {
                "clause_id": "SOP-001",
                "section": "Synthetic report fixture — all verdict treatments",
                "text": "Staff record instrument checks. <script>This is quoted SOP text.</script>",
                "char_start": 0,
                "char_end": 80,
            }
        ]
        findings = [
            make_finding(
                direction="regulation_to_sop"
                if verdict in {"addressed", "partially_addressed", "missing"}
                else "sop_to_regulation",
                verdict=verdict,
                sop_clause_refs=["SOP-001"],
                regulation_citations=[]
                if verdict in {"judge_failed", "not_covered_by_corpus"}
                else [fixture_citation],
                rationale=(
                    f"Synthetic report fixture: {verdict}. "
                    "Review the SOP beside the supplied regulation excerpt."
                ),
                requirement_strength="mandatory",
            )
            for verdict in ALL_VERDICTS
        ]
        session.add(
            GapCheckJob(
                id=REPORT_JOB_ID,
                api_key_id=WRITER_ID,
                status="completed",
                progress={
                    "phase": "completed",
                    "clauses_total": 1,
                    "clauses_done": 1,
                    "requirements_total": 1,
                    "requirements_done": 1,
                },
                report=build_report(
                    job_id=str(REPORT_JOB_ID),
                    sop_clauses=clauses,
                    findings=findings,
                    metadata={
                        "model": "fake:synthetic-report-fixture",
                        "backend": "pgvector",
                        "duration_ms": 12500,
                        "token_usage": {
                            "input_tokens": 240,
                            "output_tokens": 80,
                            "total_tokens": 320,
                        },
                        "caps": {"max_clauses": 80, "max_requirements": 120, "max_tokens": 200000},
                    },
                    caps_hit=["requirements"],
                    generated_at=now,
                ),
                created_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        await session.commit()


app = create_app()
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def browser_lifespan(application):
    await prepare_database()
    with TemporaryDirectory(prefix="docs-browser-uploads-") as uploads:
        # Settings are already isolated; source files never enter the user's upload directory.
        from pathlib import Path

        from app.core.config import settings

        settings.UPLOAD_DIR = Path(uploads)
        async with original_lifespan(application):
            await seed(application)
            yield


app.router.lifespan_context = browser_lifespan
