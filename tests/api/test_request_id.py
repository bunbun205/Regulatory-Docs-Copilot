import re

from httpx import AsyncClient

GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")


async def test_generated_request_id(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert GENERATED_ID.fullmatch(response.headers["X-Request-ID"]) is not None


async def test_supplied_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get(
        "/healthz",
        headers={"X-Request-ID": "client-id-123"},
    )
    assert response.headers["X-Request-ID"] == "client-id-123"


async def test_unsafe_supplied_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get(
        "/healthz",
        headers={"X-Request-ID": "bad id!"},
    )
    assert GENERATED_ID.fullmatch(response.headers["X-Request-ID"]) is not None
