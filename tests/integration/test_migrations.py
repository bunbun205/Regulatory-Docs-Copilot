import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def _tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        return {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }


def test_migrations_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "migrations.db"
    monkeypatch.setenv("LABDOCS_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "app" / "db" / "migrations"))

    command.upgrade(config, "head")
    assert "api_keys" in _tables(db_path)
    assert "alembic_version" in _tables(db_path)

    command.downgrade(config, "base")
    assert "api_keys" not in _tables(db_path)
