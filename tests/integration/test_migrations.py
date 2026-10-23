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
    assert {"api_keys", "documents", "chunks", "ingestion_jobs", "alembic_version"} <= tables

    async with engine.connect() as connection:
        embedding_type = await connection.scalar(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'chunks' AND column_name = 'embedding'"
            )
        )
    assert embedding_type == "vector"

    await asyncio.to_thread(command.downgrade, config, "base")
    tables = await _table_names(engine)
    assert tables.isdisjoint({"api_keys", "documents", "chunks", "ingestion_jobs"})
