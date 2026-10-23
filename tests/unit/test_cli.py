import asyncio
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import hash_api_key
from app.db.models import ApiKey
from tests.helpers import TEST_DATABASE_URL

ROOT = Path(__file__).resolve().parents[2]


def _run_cli(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "create-key",
            "--name",
            name,
            "--scope",
            "read",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "LABDOCS_DATABASE_URL": TEST_DATABASE_URL,
            "LABDOCS_LOG_LEVEL": "warning",
        },
        check=False,
    )


async def test_create_key_prints_plaintext_once_and_stores_hash(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    result = await asyncio.to_thread(_run_cli, "ci")

    assert result.returncode == 0, result.stderr
    key = result.stdout.strip()
    assert key.startswith("labdocs_")

    async with sessionmaker() as session:
        row = (
            await session.execute(select(ApiKey.key_hash, ApiKey.scope).where(ApiKey.name == "ci"))
        ).one()

    assert row.key_hash == hash_api_key(key)
    assert row.scope == "read"
    assert key != row.key_hash


async def test_create_key_rejects_duplicate_name(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    first = await asyncio.to_thread(_run_cli, "duplicate")
    second = await asyncio.to_thread(_run_cli, "duplicate")

    assert first.returncode == 0
    assert second.returncode == 1
    assert second.stdout == ""
    assert "already exists" in second.stderr

    async with sessionmaker() as session:
        keys = (await session.execute(select(ApiKey).where(ApiKey.name == "duplicate"))).all()
    assert len(keys) == 1
