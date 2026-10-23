import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.security import hash_api_key
from app.db.base import Base

ROOT = Path(__file__).resolve().parents[2]


def _create_schema(url: str) -> None:
    async def _run() -> None:
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_run())


def test_create_key_prints_plaintext_once_and_stores_hash(tmp_path: Path) -> None:
    db_path = tmp_path / "cli.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    _create_schema(url)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "create-key",
            "--name",
            "ci",
            "--scope",
            "read",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "LABDOCS_DATABASE_URL": url,
            "LABDOCS_LOG_LEVEL": "warning",
        },
        check=False,
    )

    assert result.returncode == 0, result.stderr
    key = result.stdout.strip()
    assert key.startswith("labdocs_")

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT key_hash, scope FROM api_keys WHERE name = ?",
            ("ci",),
        ).fetchone()

    assert row is not None
    assert row[0] == hash_api_key(key)
    assert row[1] == "read"
    assert key != row[0]


def test_create_key_rejects_duplicate_name(tmp_path: Path) -> None:
    db_path = tmp_path / "cli.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    _create_schema(url)
    command = [
        sys.executable,
        "-m",
        "app.cli",
        "create-key",
        "--name",
        "duplicate",
        "--scope",
        "read",
    ]
    env = {
        **os.environ,
        "LABDOCS_DATABASE_URL": url,
        "LABDOCS_LOG_LEVEL": "warning",
    }

    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env, check=False)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env, check=False)

    assert first.returncode == 0
    assert second.returncode == 1
    assert second.stdout == ""
    assert "already exists" in second.stderr
