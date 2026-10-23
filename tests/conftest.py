from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import Scope, generate_api_key, hash_api_key
from app.db.base import Base
from app.db.models import ApiKey
from app.db.session import get_session
from app.ingest.pipeline import IngestionConfig
from app.main import create_app
from tests.helpers import TEST_DATABASE_URL, FakeEmbedder


@pytest.fixture()
async def engine() -> AsyncIterator[AsyncEngine]:
    """Provide a clean Postgres database for each test.

    The test URL is guarded by ``tests.helpers`` and must end in ``_test``.
    Tests intentionally do not fall back to SQLite: vector columns, upserts and
    idempotency must be exercised against the real Postgres dialect.
    """
    db_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with db_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await connection.run_sync(Base.metadata.create_all)

    yield db_engine

    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await db_engine.dispose()


@pytest.fixture()
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture()
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture()
def ingestion_config() -> IngestionConfig:
    return IngestionConfig(max_file_bytes=1024 * 1024)


@pytest.fixture()
def app(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> FastAPI:
    application = create_app()
    application.state.sessionmaker = sessionmaker
    application.state.embedder = fake_embedder
    application.state.ingestion_config = ingestion_config
    application.state.upload_dir = tmp_path / "uploads"

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session
    return application


@pytest.fixture()
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture()
def make_api_key(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[str]]:
    async def _make_api_key(name: str = "test-key", scope: Scope = Scope.READ) -> str:
        plaintext = generate_api_key()
        async with sessionmaker() as session:
            session.add(
                ApiKey(
                    name=name,
                    key_hash=hash_api_key(plaintext),
                    scope=scope.value,
                )
            )
            await session.commit()
        return plaintext

    return _make_api_key


@pytest.fixture()
def sample_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "sample"
