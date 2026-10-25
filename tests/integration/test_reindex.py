import hashlib
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli import _reindex_qdrant
from app.db.models import EMBEDDING_DIMENSION
from app.store.base import VectorRecord
from app.store.pgvector_store import PgVectorStore
from app.store.qdrant_store import QdrantStore


def _unit_vector(index: int) -> tuple[float, ...]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = 1.0
    return tuple(vector)


def _record(key: str, *, vector_index: int) -> VectorRecord:
    document_id = uuid5(NAMESPACE_URL, f"reindex-document-{key}")
    return VectorRecord(
        chunk_id=uuid5(NAMESPACE_URL, f"reindex-chunk-{key}"),
        document_id=document_id,
        chunk_index=0,
        text=f"Reindex text {key}",
        token_count=3,
        page=None,
        section_heading=None,
        embedding=_unit_vector(vector_index),
        filename=f"{key}.txt",
        title=f"Reindex {key}",
        source_agency="Synthetic Agency",
        doc_type="regulation",
        year=2024,
        version="v1",
        content_sha256=hashlib.sha256(key.encode()).hexdigest(),
        byte_size=10,
        page_count=1,
    )


async def test_reindex_qdrant_rebuilds_from_postgres_and_drops_stale_points(
    sessionmaker: async_sessionmaker[AsyncSession],
    qdrant_store: QdrantStore,
) -> None:
    records = [
        _record("a", vector_index=0),
        _record("b", vector_index=1),
        _record("c", vector_index=2),
    ]
    pg_store = PgVectorStore(sessionmaker)
    await pg_store.upsert(records)

    stale = _record("stale", vector_index=3)
    await qdrant_store.upsert([stale])
    assert await qdrant_store.count() == 1

    summary = await _reindex_qdrant(pg_store, qdrant_store)

    assert summary == {
        "backend": "qdrant",
        "collection": qdrant_store.collection,
        "documents": 3,
        "chunks": 3,
    }
    assert await qdrant_store.count() == 3
    hits = await qdrant_store.search(_unit_vector(0), top_k=10)
    assert {hit.chunk_id for hit in hits} == {record.chunk_id for record in records}
    assert stale.chunk_id not in {hit.chunk_id for hit in hits}

    second_summary = await _reindex_qdrant(pg_store, qdrant_store)
    assert second_summary == summary
    assert await qdrant_store.count() == 3
