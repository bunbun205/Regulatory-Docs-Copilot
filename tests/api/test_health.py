from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


async def test_readyz_database_ok(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


class _BrokenSession:
    async def __aenter__(self) -> "_BrokenSession":
        raise RuntimeError("database unavailable")

    async def __aexit__(self, *args: object) -> None:
        return None


class _BrokenSessionmaker:
    def __call__(self) -> _BrokenSession:
        return _BrokenSession()


async def test_readyz_database_unavailable(app: FastAPI) -> None:
    app.state.sessionmaker = _BrokenSessionmaker()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "checks": {"database": "unavailable"},
    }


async def test_metrics(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "python_info" in response.text
