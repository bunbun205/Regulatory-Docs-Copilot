import asyncio
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from app.core.security import Scope


async def _upload(
    client: AsyncClient,
    key: str,
    *,
    content: str,
    title: str,
    source_agency: str,
    doc_type: str,
    year: str = "2024",
) -> str:
    response = await client.post(
        "/v1/documents",
        headers={"X-API-Key": key},
        files={"file": ("synthetic-search.txt", content.encode(), "text/plain")},
        data={
            "title": title,
            "source_agency": source_agency,
            "doc_type": doc_type,
            "year": year,
            "version": "v1",
        },
    )
    assert response.status_code == 202
    return str(response.json()["job_id"])


async def _wait_for_job(client: AsyncClient, key: str, job_id: str) -> None:
    for _ in range(500):
        response = await client.get(f"/v1/jobs/{job_id}", headers={"X-API-Key": key})
        assert response.status_code == 200
        if response.json()["status"] in {"completed", "failed"}:
            assert response.json()["status"] == "completed"
            return
        await asyncio.sleep(0.01)
    raise AssertionError("ingestion job did not finish")


async def test_search_pgvector_returns_chunks_and_metadata(
    client: AsyncClient,
    make_api_key: Any,
) -> None:
    key = await make_api_key(scope=Scope.WRITE)
    content = f"Synthetic retention schedule {uuid4()}."
    job_id = await _upload(
        client,
        key,
        content=content,
        title="Synthetic Retention Policy",
        source_agency="Synthetic Agency",
        doc_type="guidance",
        year="2022",
    )
    await _wait_for_job(client, key, job_id)

    response = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "retention schedule", "top_k": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "pgvector"
    assert payload["top_k"] == 5
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["title"] == "Synthetic Retention Policy"
    assert result["filename"] == "synthetic-search.txt"
    assert result["doc_type"] == "guidance"
    assert result["source_agency"] == "Synthetic Agency"
    assert result["year"] == 2022
    assert result["text"] == content
    assert isinstance(result["score"], float)
    assert payload["latency_ms"] >= 0


async def test_search_filters_and_top_k(
    client: AsyncClient,
    make_api_key: Any,
) -> None:
    key = await make_api_key(scope=Scope.WRITE)
    for doc_type, agency, year in [
        ("guidance", "Synthetic Agency", "2022"),
        ("regulation", "Other Agency", "2015"),
    ]:
        job_id = await _upload(
            client,
            key,
            content=f"Synthetic search filter text {doc_type} {uuid4()}",
            title=f"Synthetic {doc_type}",
            source_agency=agency,
            doc_type=doc_type,
            year=year,
        )
        await _wait_for_job(client, key, job_id)

    filtered = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={
            "query": "synthetic filter",
            "top_k": 10,
            "filters": {"doc_type": "guidance", "year_min": 2020},
        },
    )
    assert filtered.status_code == 200
    assert [item["doc_type"] for item in filtered.json()["results"]] == ["guidance"]

    limited = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "synthetic filter", "top_k": 1},
    )
    assert limited.status_code == 200
    assert len(limited.json()["results"]) == 1


async def test_search_empty_index_and_validation(
    client: AsyncClient,
    make_api_key: Any,
) -> None:
    key = await make_api_key()
    empty = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "nothing indexed"},
    )
    assert empty.status_code == 200
    assert empty.json()["results"] == []

    blank = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "   "},
    )
    assert blank.status_code == 422

    bad_range = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={
            "query": "anything",
            "filters": {"year_min": 2025, "year_max": 2020},
        },
    )
    assert bad_range.status_code == 422

    unknown_filter = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "anything", "filters": {"agency": "FDA"}},
    )
    assert unknown_filter.status_code == 422

    too_many = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "anything", "top_k": 51},
    )
    assert too_many.status_code == 422

    bad_backend = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "anything", "backend": "weaviate"},
    )
    assert bad_backend.status_code == 422

    unconfigured = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "anything", "backend": "qdrant"},
    )
    assert unconfigured.status_code == 422
    assert unconfigured.json()["error"]["code"] == "backend_unavailable"


async def test_search_requires_read_scope(client: AsyncClient) -> None:
    response = await client.post("/v1/search", json={"query": "anything"})
    assert response.status_code == 401


async def test_search_qdrant_backend_uses_ingestion_fanout(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Any,
    qdrant_store: Any,
) -> None:
    app.state.vector_stores["qdrant"] = qdrant_store
    app.state.ingestion_vector_stores = (qdrant_store,)
    key = await make_api_key(scope=Scope.WRITE)
    content = f"Synthetic Qdrant retrieval text {uuid4()}."
    job_id = await _upload(
        client,
        key,
        content=content,
        title="Synthetic Qdrant Document",
        source_agency="Synthetic Agency",
        doc_type="guidance",
    )
    await _wait_for_job(client, key, job_id)

    response = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "qdrant retrieval", "backend": "qdrant"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "qdrant"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["text"] == content

    # A duplicate re-ingest must repair a missing external vector index.
    await qdrant_store.delete_collection()
    second_job = await _upload(
        client,
        key,
        content=content,
        title="Synthetic Qdrant Document",
        source_agency="Synthetic Agency",
        doc_type="guidance",
    )
    await _wait_for_job(client, key, second_job)
    repaired = await client.post(
        "/v1/search",
        headers={"X-API-Key": key},
        json={"query": "qdrant retrieval", "backend": "qdrant"},
    )
    assert repaired.status_code == 200
    assert len(repaired.json()["results"]) == 1


async def test_search_reports_unavailable_embedding_and_store(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Any,
) -> None:
    key = await make_api_key()

    class BrokenEmbedder:
        dimension = 384

        def embed(self, texts: list[str]) -> Any:
            raise RuntimeError("embedding unavailable")

    original_embedder = app.state.embedder
    app.state.embedder = BrokenEmbedder()
    try:
        response = await client.post(
            "/v1/search",
            headers={"X-API-Key": key},
            json={"query": "anything"},
        )
    finally:
        app.state.embedder = original_embedder
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "embedding_unavailable"

    class BrokenStore:
        name = "broken"

        async def search(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("store unavailable")

    app.state.vector_stores["pgvector"] = BrokenStore()
    try:
        response = await client.post(
            "/v1/search",
            headers={"X-API-Key": key},
            json={"query": "anything"},
        )
    finally:
        app.state.vector_stores.pop("pgvector", None)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "vector_store_unavailable"
