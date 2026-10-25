import hashlib
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import EMBEDDING_DIMENSION
from app.store.base import SearchFilters, VectorRecord
from app.store.pgvector_store import PgVectorStore
from tests.helpers import TEST_DATABASE_URL


def _unit_vector(index: int) -> tuple[float, ...]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = 1.0
    return tuple(vector)


def _record(
    *,
    document_id: UUID,
    chunk_index: int,
    vector: tuple[float, ...],
    source_agency: str,
) -> VectorRecord:
    return VectorRecord(
        chunk_id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        text=f"{source_agency} chunk {chunk_index}",
        token_count=3,
        page=None,
        section_heading=None,
        embedding=vector,
        filename=f"{document_id}.txt",
        title=f"{source_agency} document",
        source_agency=source_agency,
        doc_type="regulation",
        year=2024,
        version="v1",
        content_sha256=hashlib.sha256(str(document_id).encode()).hexdigest(),
        byte_size=10,
        page_count=1,
    )


async def test_filtered_search_returns_all_matches_with_hnsw(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """A selective filter must not be lost in HNSW post-filtering.

    The rare document is orthogonal to the query while 499 other documents
    dominate the nearest-neighbor candidate set.  ``enable_seqscan=off`` forces
    the initial query to use the HNSW index. The store may then take its
    correctness fallback if the approximate result under-returns.
    """
    store = PgVectorStore(sessionmaker)
    common_vector = _unit_vector(0)
    rare_vector = _unit_vector(EMBEDDING_DIMENSION - 1)
    rare_document_id = uuid4()

    records: list[VectorRecord] = []
    for document_number in range(500):
        document_id = rare_document_id if document_number == 0 else uuid4()
        source_agency = "Rare Agency" if document_number == 0 else "Common Agency"
        vector = rare_vector if document_number == 0 else common_vector
        for chunk_index in range(5):
            records.append(
                _record(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    vector=vector,
                    source_agency=source_agency,
                )
            )
    await store.upsert(records)

    index_engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"server_settings": {"enable_seqscan": "off"}},
    )
    index_sessionmaker = async_sessionmaker(index_engine, expire_on_commit=False)
    try:
        hits = await PgVectorStore(index_sessionmaker).search(
            common_vector,
            50,
            SearchFilters(source_agency="Rare Agency"),
        )
    finally:
        await index_engine.dispose()

    assert len(hits) == 5
    assert {hit.document_id for hit in hits} == {rare_document_id}
    assert [hit.chunk_index for hit in hits] == [0, 1, 2, 3, 4]
