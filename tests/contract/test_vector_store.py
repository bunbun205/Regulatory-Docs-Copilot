import hashlib
from typing import cast
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.store.base import SearchFilters, VectorRecord, VectorStore
from app.store.pgvector_store import PgVectorStore


def _unit_vector(index: int) -> tuple[float, ...]:
    vector = [0.0] * 384
    vector[index] = 1.0
    return tuple(vector)


def _record(
    key: str,
    *,
    vector_index: int,
    doc_type: str = "regulation",
    source_agency: str = "FDA",
    year: int = 2020,
    title: str = "Synthetic regulation",
    text: str = "Synthetic retrieval text.",
    page: int | None = 1,
    section_heading: str | None = "Scope",
) -> VectorRecord:
    document_id = uuid5(NAMESPACE_URL, f"document-{key}")
    return VectorRecord(
        chunk_id=uuid5(NAMESPACE_URL, f"chunk-{key}"),
        document_id=document_id,
        chunk_index=0,
        text=text,
        token_count=4,
        page=page,
        section_heading=section_heading,
        embedding=_unit_vector(vector_index),
        filename=f"{key}.pdf",
        title=title,
        source_agency=source_agency,
        doc_type=doc_type,
        year=year,
        version="v1",
        content_sha256=hashlib.sha256(key.encode()).hexdigest(),
        byte_size=len(text),
        page_count=1,
    )


@pytest.fixture(params=["pgvector", "qdrant"])
def store(
    request: pytest.FixtureRequest,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> VectorStore:
    if request.param == "pgvector":
        return PgVectorStore(sessionmaker)
    return cast(VectorStore, request.getfixturevalue("qdrant_store"))


async def test_upsert_is_idempotent_and_search_orders_by_score(
    store: VectorStore,
) -> None:
    records = [
        _record("a", vector_index=0, title="Alpha"),
        _record("b", vector_index=1, title="Beta"),
        _record("c", vector_index=2, title="Gamma"),
    ]
    await store.upsert(records)
    await store.upsert(records)

    assert await store.count() == 3
    hits = await store.search(_unit_vector(0), top_k=10)
    assert hits[0].chunk_id == records[0].chunk_id
    assert {hit.chunk_id for hit in hits[1:]} == {
        records[1].chunk_id,
        records[2].chunk_id,
    }
    assert [hit.score for hit in hits] == sorted(
        (hit.score for hit in hits),
        reverse=True,
    )
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].title == "Alpha"
    assert hits[0].filename == "a.pdf"
    assert hits[0].page == 1
    assert hits[0].section_heading == "Scope"

    limited = await store.search(_unit_vector(0), top_k=2)
    assert len(limited) == 2


async def test_filters_are_applied_on_both_backends(store: VectorStore) -> None:
    await store.upsert(
        [
            _record("a", vector_index=0, doc_type="regulation", source_agency="FDA", year=2020),
            _record("b", vector_index=1, doc_type="guidance", source_agency="FDA", year=2010),
            _record("c", vector_index=2, doc_type="regulation", source_agency="OSHA", year=2024),
        ]
    )

    by_type = await store.search(
        _unit_vector(0),
        top_k=10,
        filters=SearchFilters(doc_type="regulation"),
    )
    assert {hit.filename for hit in by_type} == {"a.pdf", "c.pdf"}

    by_agency = await store.search(
        _unit_vector(0),
        top_k=10,
        filters=SearchFilters(source_agency="FDA"),
    )
    assert {hit.filename for hit in by_agency} == {"a.pdf", "b.pdf"}

    by_year = await store.search(
        _unit_vector(0),
        top_k=10,
        filters=SearchFilters(year_min=2012, year_max=2024),
    )
    assert {hit.filename for hit in by_year} == {"a.pdf", "c.pdf"}

    combined = await store.search(
        _unit_vector(0),
        top_k=10,
        filters=SearchFilters(
            doc_type="regulation",
            source_agency="OSHA",
            year_min=2021,
        ),
    )
    assert [hit.filename for hit in combined] == ["c.pdf"]


async def test_delete_document_removes_only_that_document(
    store: VectorStore,
) -> None:
    first = _record("a", vector_index=0)
    second = _record("b", vector_index=1)
    await store.upsert([first, second])

    removed = await store.delete_document(first.document_id)
    assert removed == 1
    assert await store.count() == 1

    hits = await store.search(_unit_vector(0), top_k=10)
    assert [hit.document_id for hit in hits] == [second.document_id]
    assert await store.delete_document(first.document_id) == 0


async def test_empty_store_and_query_validation(store: VectorStore) -> None:
    assert await store.count() == 0
    assert await store.search(_unit_vector(0), top_k=5) == []

    with pytest.raises(ValueError):
        await store.search([0.0] * 383, top_k=5)
    with pytest.raises(ValueError):
        await store.search(_unit_vector(0), top_k=0)
    with pytest.raises(ValueError):
        SearchFilters(year_min=2020, year_max=2010)
