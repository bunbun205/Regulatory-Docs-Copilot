"""Isolated browser-test entrypoint. Never import this from production app code.

Run with uvicorn frontend.e2e.server:app. It resets only its dedicated _test DB
and collection. Fixed test credentials are confined to those isolated stores.
"""

# ruff: noqa: E402
import hashlib
import json
import os
import re
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
from app.gapcheck.report import build_report
from app.llm.fake import FakeLLM
from app.main import create_app
from app.store.base import VectorRecord
from tests.helpers import FakeEmbedder

WRITE_KEY = "frontend-e2e-write"
READ_KEY = "frontend-e2e-read"
WRITER_ID = UUID("10000000-0000-4000-8000-000000000001")
JOB_ID = UUID("10000000-0000-4000-8000-000000000003")
CHUNK_ID = UUID("10000000-0000-4000-8000-000000000004")
SOURCE = "Staff must record instrument checks in a training log before using the equipment."


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
    # F1 exercises auth/navigation/errors. Later milestones extend scripted tool/judge flows here.
    application.state.llm_client = FakeLLM(
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
