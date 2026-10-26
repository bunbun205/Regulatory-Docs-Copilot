import asyncio
from uuid import uuid4

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.rate_limit import TokenBucketRateLimiter
from app.main import create_app


async def test_rate_limit_auth_isolation_refill_and_observability(client, app, make_api_key):
    now = [0.0]
    app.state.rate_limiter = TokenBucketRateLimiter(2, clock=lambda: now[0])
    key = await make_api_key(name="limited")
    other = await make_api_key(name="other")
    for _ in range(3):
        assert (await client.get("/v1/whoami", headers={"X-API-Key": "invalid"})).status_code == 401
    assert not app.state.rate_limiter._buckets
    headers = {"X-API-Key": key, "X-Request-ID": "limit-request"}
    assert (await client.get("/v1/whoami", headers=headers)).status_code == 200
    assert (await client.get("/v1/whoami", headers=headers)).status_code == 200
    response = await client.get("/v1/whoami", headers=headers)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.headers["X-Request-ID"] == "limit-request"
    assert response.json()["error"]["request_id"] == "limit-request"
    assert response.json()["error"]["code"] == "rate_limited"
    assert (await client.get("/v1/whoami", headers={"X-API-Key": other})).status_code == 200
    assert key not in app.state.rate_limiter._buckets
    metrics = (await client.get("/metrics")).text
    assert 'endpoint="/v1/whoami",method="GET",status_code="429"} 1.0' in metrics
    now[0] = 30
    assert (await client.get("/v1/whoami", headers=headers)).status_code == 200
    assert (await client.get("/v1/whoami", headers=headers)).status_code == 429


async def test_concurrent_requests_cannot_bypass_limiter(client, app, make_api_key):
    app.state.rate_limiter = TokenBucketRateLimiter(2)
    key = await make_api_key()
    responses = await asyncio.gather(
        *(client.get("/v1/whoami", headers={"X-API-Key": key}) for _ in range(8))
    )
    assert sorted(r.status_code for r in responses) == [200, 200] + [429] * 6


async def test_metrics_use_route_templates_and_bound_unknown_paths(client, app, make_api_key):
    key = await make_api_key()
    for _ in range(3):
        assert (
            await client.get(f"/v1/documents/{uuid4()}", headers={"X-API-Key": key})
        ).status_code == 404
        assert (await client.get(f"/unknown-{uuid4()}")).status_code == 404
    metrics = (await client.get("/metrics")).text
    assert 'endpoint="/v1/documents/{document_id}"' in metrics
    assert 'endpoint="unmatched",method="GET",status_code="404"} 3.0' in metrics
    assert "/unknown-" not in metrics
    assert "http_request_duration_seconds_count" in metrics
    assert (await client.get("/metrics")).text == metrics


async def test_unhandled_errors_are_counted_with_request_id(app):
    @app.get("/fail")
    async def fail():
        raise RuntimeError("test failure")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/fail", headers={"X-Request-ID": "server-error"})
        assert response.status_code == 500
        assert response.json()["error"]["request_id"] == "server-error"
        assert response.headers["X-Request-ID"] == "server-error"
        metrics = (await client.get("/metrics")).text
        assert 'endpoint="/fail",method="GET",status_code="500"} 1.0' in metrics


@pytest.mark.parametrize("declared", [None, "1", "65"])
async def test_body_limit_rejects_before_handler_even_without_honest_length(monkeypatch, declared):
    monkeypatch.setattr(settings, "MAX_REQUEST_BYTES", 64)
    application = create_app()
    invoked = []

    @application.post("/body")
    async def body(request: Request):
        invoked.append(True)
        return {"size": len(await request.body())}

    async def chunks():
        yield b"a" * 32
        yield b"b" * 33

    headers = {"X-Request-ID": "body-limit"}
    if declared is not None:
        headers["Content-Length"] = declared
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/body", content=chunks(), headers=headers)
        assert response.status_code == 413
        assert response.json()["error"]["request_id"] == "body-limit"
        assert response.headers["X-Request-ID"] == "body-limit"
        assert not invoked
        metrics = (await client.get("/metrics")).text
        assert 'status_code="413"} 1.0' in metrics
        response = await client.post("/body", content=b"x" * 64)
        assert response.status_code == 200
        assert response.json()["size"] == 64


@pytest.mark.parametrize("length", ["-1", "no", "1, 1", "9" * 5000])
async def test_body_limit_validates_length_without_crashing(monkeypatch, length):
    monkeypatch.setattr(settings, "MAX_REQUEST_BYTES", 64)
    application = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/v1/search", content=b"x", headers={"Content-Length": length})
    assert response.status_code == (413 if length.isdigit() else 400)


def test_per_key_job_setting_matches_database_constraint():
    with pytest.raises(ValidationError):
        Settings(GAPCHECK_MAX_CONCURRENT_JOBS_PER_KEY=2)


async def test_simultaneous_gap_job_creation_is_atomic(sessionmaker, make_api_key):
    from sqlalchemy import select

    from app.db.models import ApiKey
    from app.gapcheck.jobs import GapCheckLimitError, create_gapcheck_job

    await make_api_key()
    async with sessionmaker() as session:
        key = await session.scalar(select(ApiKey))
    results = await asyncio.gather(
        *(create_gapcheck_job(sessionmaker, key.id) for _ in range(4)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, GapCheckLimitError) for result in results) == 3
    assert sum(not isinstance(result, Exception) for result in results) == 1
