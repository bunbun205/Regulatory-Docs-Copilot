import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base
from tests.helpers import TEST_DATABASE_URL

ROOT = Path(__file__).resolve().parents[2]


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))


async def test_migrations_upgrade_and_downgrade(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    monkeypatch.setenv("LABDOCS_DATABASE_URL", TEST_DATABASE_URL)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "app" / "db" / "migrations"))

    await asyncio.to_thread(command.upgrade, config, "head")
    tables = await _table_names(engine)
    assert {
        "api_keys",
        "documents",
        "chunks",
        "ingestion_jobs",
        "gapcheck_jobs",
        "gapcheck_judgement_cache",
        "alembic_version",
    } <= tables

    async with engine.connect() as connection:
        embedding_type = await connection.scalar(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'chunks' AND column_name = 'embedding'"
            )
        )
    assert embedding_type == "vector"

    async with engine.connect() as connection:
        index_definition = await connection.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
        )
    assert index_definition is not None
    assert "USING hnsw" in index_definition
    assert "vector_cosine_ops" in index_definition

    async with engine.connect() as connection:
        identity_constraint = await connection.scalar(
            text("SELECT conname FROM pg_constraint WHERE conname = 'uq_documents_agency_filename'")
        )
    assert identity_constraint == "uq_documents_agency_filename"

    async with engine.connect() as connection:
        gapcheck_index = await connection.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_gapcheck_jobs_key_status'")
        )
    assert gapcheck_index is not None
    assert "api_key_id" in gapcheck_index
    assert "status" in gapcheck_index

    async with engine.connect() as connection:
        active_index = await connection.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_gapcheck_jobs_active_key'")
        )
    assert active_index is not None
    assert "UNIQUE" in active_index
    assert "status" in active_index

    async with engine.connect() as connection:
        gapcheck_fk = await connection.scalar(
            text(
                "SELECT confdeltype FROM pg_constraint "
                "WHERE conname = 'fk_gapcheck_jobs_api_key_id_api_keys'"
            )
        )
    assert gapcheck_fk in {b"c", "c"}

    await asyncio.to_thread(command.downgrade, config, "base")
    tables = await _table_names(engine)
    assert tables.isdisjoint(
        {
            "api_keys",
            "documents",
            "chunks",
            "ingestion_jobs",
            "gapcheck_jobs",
            "gapcheck_judgement_cache",
        }
    )
