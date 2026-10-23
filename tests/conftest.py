import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
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
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("LABDOCS_TEST_DATABASE_URL")


@pytest.fixture()
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Provide a clean database. SQLite locally, real Postgres when configured."""
    if TEST_DATABASE_URL:
        db_engine = create_async_engine(TEST_DATABASE_URL)
        async with db_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    else:
        db_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
        async with db_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    yield db_engine

    if TEST_DATABASE_URL:
        async with db_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    await db_engine.dispose()


@pytest.fixture()
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture()
def app(sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    application = create_app()
    application.state.sessionmaker = sessionmaker

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
