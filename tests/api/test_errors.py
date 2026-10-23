from fastapi import FastAPI, Query
from httpx import ASGITransport, AsyncClient


async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/v1/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_validation_error_uses_envelope(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    @app.get("/v1/_test/validated")
    async def validated(count: int = Query(...)) -> dict[str, int]:
        return {"count": count}

    response = await client.get("/v1/_test/validated", params={"count": "nope"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_unhandled_error_returns_500_envelope_without_details(
    app: FastAPI,
) -> None:
    @app.get("/v1/_test/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/_test/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]
