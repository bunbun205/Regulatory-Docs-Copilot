import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import Scope
from app.main import create_app
from app.store.qdrant_store import QdrantStore
from tests.helpers import TEST_DATABASE_URL, TEST_QDRANT_URL, FakeEmbedder


async def test_real_lifespan_wires_database_embedder_and_qdrant(
    make_api_key: Any,
    fake_embedder: FakeEmbedder,
    qdrant_store: QdrantStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "both")
    monkeypatch.setattr(settings, "QDRANT_URL", TEST_QDRANT_URL)
    monkeypatch.setattr(settings, "QDRANT_COLLECTION", qdrant_store.collection)
    monkeypatch.setattr(
        "app.main.SentenceTransformerEmbedder",
        lambda *args, **kwargs: fake_embedder,
    )

    application = create_app()
    async with application.router.lifespan_context(application):
        assert application.state.embedder is fake_embedder
        assert application.state.embedder_ready is True
        assert fake_embedder.calls == 1
        assert application.state.default_vector_backend == "pgvector"
        assert set(application.state.vector_stores) == {"pgvector", "qdrant"}
        assert application.state.ingestion_vector_stores == (
            application.state.vector_stores["qdrant"],
        )

        key = await make_api_key(scope=Scope.WRITE)
        content = f"Lifespan wiring searchable text {uuid4()}."
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            upload = await client.post(
                "/v1/documents",
                headers={"X-API-Key": key},
                files={"file": ("lifespan.txt", content.encode(), "text/plain")},
                data={
                    "title": "Lifespan wiring",
                    "source_agency": "Synthetic Agency",
                    "doc_type": "guidance",
                    "year": "2024",
                    "version": "v1",
                },
            )
            assert upload.status_code == 202
            job_id = upload.json()["job_id"]
            for _ in range(500):
                job = await client.get(
                    f"/v1/jobs/{job_id}",
                    headers={"X-API-Key": key},
                )
                assert job.status_code == 200
                if job.json()["status"] in {"completed", "failed"}:
                    assert job.json()["status"] == "completed"
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("lifespan ingestion job did not finish")

            response = await client.post(
                "/v1/search",
                headers={"X-API-Key": key},
                json={"query": "lifespan wiring", "backend": "qdrant"},
            )
            assert response.status_code == 200
            assert response.json()["backend"] == "qdrant"
            assert [result["text"] for result in response.json()["results"]] == [content]

        assert await qdrant_store.count() > 0


async def test_embedding_load_failure_prevents_startup(make_api_key, monkeypatch, tmp_path):
    import pytest

    class BrokenEmbedder(FakeEmbedder):
        def embed(self, texts):
            raise RuntimeError("embedding load failed")

    monkeypatch.setattr(settings, "DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "pgvector")
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.main.SentenceTransformerEmbedder", lambda *a, **k: BrokenEmbedder())
    application = create_app()
    with pytest.raises(RuntimeError, match="embedding load failed"):
        async with application.router.lifespan_context(application):
            raise AssertionError("Startup incorrectly succeeded")
    assert application.state.embedder_ready is False
