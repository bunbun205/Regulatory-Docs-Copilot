import hashlib
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import EMBEDDING_DIMENSION
from app.store.base import VectorRecord
from app.store.pgvector_store import PgVectorStore
from app.store.qdrant_store import QdrantStore


def _unit_vector(index: int) -> tuple[float, ...]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = 1.0
    return tuple(vector)


def _record(key: str, vector_index: int) -> VectorRecord:
    document_id = uuid5(NAMESPACE_URL, f"score-document-{key}")
    return VectorRecord(
        chunk_id=uuid5(NAMESPACE_URL, f"score-chunk-{key}"),
        document_id=document_id,
        chunk_index=0,
        text=f"Score parity text {key}",
        token_count=4,
        page=None,
        section_heading=None,
        embedding=_unit_vector(vector_index),
        filename=f"{key}.txt",
        title=f"Score parity {key}",
        source_agency="Synthetic Agency",
        doc_type="regulation",
        year=2024,
        version="v1",
        content_sha256=hashlib.sha256(key.encode()).hexdigest(),
        byte_size=10,
        page_count=1,
    )


async def test_both_stores_use_the_same_cosine_similarity_scale(
    sessionmaker: async_sessionmaker[AsyncSession],
    qdrant_store: QdrantStore,
) -> None:
    records = [
        _record("same", 0),
        _record("orthogonal-a", 1),
        _record("orthogonal-b", 2),
    ]
    pg_store = PgVectorStore(sessionmaker)
    await pg_store.upsert(records)
    await qdrant_store.upsert(records)

    query = _unit_vector(0)
    pg_hits = await pg_store.search(query, top_k=10)
    qdrant_hits = await qdrant_store.search(query, top_k=10)

    pg_scores = {hit.chunk_id: hit.score for hit in pg_hits}
    qdrant_scores = {hit.chunk_id: hit.score for hit in qdrant_hits}

    assert set(pg_scores) == set(qdrant_scores)
    for chunk_id, pg_score in pg_scores.items():
        assert pg_score == pytest.approx(qdrant_scores[chunk_id], abs=1e-5)
        assert -1.0 <= pg_score <= 1.0
        assert -1.0 <= qdrant_scores[chunk_id] <= 1.0

    same = records[0].chunk_id
    assert pg_scores[same] == pytest.approx(1.0, abs=1e-5)
    assert qdrant_scores[same] == pytest.approx(1.0, abs=1e-5)
    assert pg_scores[records[1].chunk_id] == pytest.approx(0.0, abs=1e-5)
    assert qdrant_scores[records[1].chunk_id] == pytest.approx(0.0, abs=1e-5)

    assert [hit.score for hit in pg_hits] == sorted(
        (hit.score for hit in pg_hits),
        reverse=True,
    )
    assert [hit.score for hit in qdrant_hits] == sorted(
        (hit.score for hit in qdrant_hits),
        reverse=True,
    )
