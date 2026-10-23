from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.api.deps import require_scope
from app.core.security import Scope
from app.db.models import ApiKey


async def test_missing_key_returns_401_envelope(client: AsyncClient) -> None:
    response = await client.get("/v1/whoami")
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "unauthorized"
    assert error["message"] == "Missing API key."
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_invalid_key_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/v1/whoami",
        headers={"X-API-Key": "labdocs_not-a-real-key"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_whoami_returns_read_scope(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    key = await make_api_key(name="reader", scope=Scope.READ)
    response = await client.get("/v1/whoami", headers={"X-API-Key": key})
    assert response.status_code == 200
    assert response.json() == {"name": "reader", "scopes": ["read"]}


async def test_whoami_write_key_has_read_and_write_scopes(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    key = await make_api_key(name="writer", scope=Scope.WRITE)
    response = await client.get("/v1/whoami", headers={"X-API-Key": key})
    assert response.status_code == 200
    assert response.json() == {"name": "writer", "scopes": ["read", "write"]}


async def test_read_key_forbidden_on_write_dependency(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    @app.get("/v1/_test/write-read-key")
    async def write_route(
        _: Annotated[ApiKey, Depends(require_scope(Scope.WRITE))],
    ) -> dict[str, bool]:
        return {"ok": True}

    key = await make_api_key(name="read-only", scope=Scope.READ)
    response = await client.get(
        "/v1/_test/write-read-key",
        headers={"X-API-Key": key},
    )
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "forbidden"
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_write_key_allowed_on_write_dependency(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    @app.get("/v1/_test/write-write-key")
    async def write_route(
        _: Annotated[ApiKey, Depends(require_scope(Scope.WRITE))],
    ) -> dict[str, bool]:
        return {"ok": True}

    key = await make_api_key(name="writer-2", scope=Scope.WRITE)
    response = await client.get(
        "/v1/_test/write-write-key",
        headers={"X-API-Key": key},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
