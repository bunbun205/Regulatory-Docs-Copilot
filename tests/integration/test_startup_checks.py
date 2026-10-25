from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.main import create_app
from app.store.qdrant_store import QdrantStore
from tests.helpers import TEST_DATABASE_URL, TEST_QDRANT_URL, FakeEmbedder


async def test_qdrant_collection_dimension_mismatch_fails_loudly() -> None:
    collection = f"labdocs_dimension_test_{uuid4().hex}"
    small = QdrantStore(TEST_QDRANT_URL, collection, dimension=3)
    large = QdrantStore(TEST_QDRANT_URL, collection, dimension=384)
    try:
        await small.ensure_ready()
        with pytest.raises(RuntimeError, match="dimension"):
            await large.ensure_ready()
    finally:
        with suppress(Exception):
            await small.delete_collection()
        await small.close()
        await large.close()


async def test_qdrant_collection_distance_mismatch_fails_loudly() -> None:
    collection = f"labdocs_distance_test_{uuid4().hex}"
    client = AsyncQdrantClient(url=TEST_QDRANT_URL)
    store = QdrantStore(TEST_QDRANT_URL, collection, dimension=384)
    try:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=384, distance=Distance.DOT),
        )
        with pytest.raises(RuntimeError, match="cosine"):
            await store.ensure_ready()
    finally:
        with suppress(Exception):
            await client.delete_collection(collection)
        await client.close()
        await store.close()


async def test_lifespan_rejects_embedder_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 128)
    application = create_app()
    with pytest.raises(RuntimeError, match="EMBEDDING_DIMENSION"):
        async with application.router.lifespan_context(application):
            pass


async def test_lifespan_rejects_qdrant_collection_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection = f"labdocs_lifespan_dimension_test_{uuid4().hex}"
    client = AsyncQdrantClient(url=TEST_QDRANT_URL)
    try:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=3, distance=Distance.COSINE),
        )
        monkeypatch.setattr(settings, "DATABASE_URL", TEST_DATABASE_URL)
        monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
        monkeypatch.setattr(settings, "VECTOR_BACKEND", "both")
        monkeypatch.setattr(settings, "QDRANT_URL", TEST_QDRANT_URL)
        monkeypatch.setattr(settings, "QDRANT_COLLECTION", collection)
        monkeypatch.setattr(
            "app.main.SentenceTransformerEmbedder",
            lambda *args, **kwargs: FakeEmbedder(),
        )
        application = create_app()
        with pytest.raises(RuntimeError, match="dimension"):
            async with application.router.lifespan_context(application):
                pass
    finally:
        with suppress(Exception):
            await client.delete_collection(collection)
        await client.close()
