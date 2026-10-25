from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Chunk, Document, IngestionJob
from app.ingest.pipeline import (
    DocumentMetadata,
    IngestionConfig,
    IngestionJobError,
    IngestionPipeline,
    create_ingestion_job,
)
from app.store.qdrant_store import QdrantStore
from tests.helpers import FakeEmbedder


async def test_sample_manifest_ingestion_is_idempotent(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    sample_dir: Path,
) -> None:
    pipeline = IngestionPipeline(sessionmaker, fake_embedder, ingestion_config)
    manifest_path = sample_dir / "manifest.csv"

    first_job = await create_ingestion_job(sessionmaker)
    first_report = await pipeline.run_manifest_job(first_job, manifest_path, sample_dir)

    assert first_report["documents_total"] == 4
    assert first_report["documents_ingested"] == 3
    assert first_report["documents_duplicate"] == 1
    assert first_report["documents_failed"] == 0
    assert first_report["chunks"] > 0
    assert first_report["chunk_length"]["count"] == first_report["chunks"]
    assert first_report["failures"] == []
    assert {row["row"] for row in first_report["rejected_rows"]} == {6, 7, 8}
    assert fake_embedder.calls == 3

    async with sessionmaker() as session:
        first_job_row = await session.get(IngestionJob, first_job)
        assert first_job_row is not None
        assert first_job_row.status == "completed"
        assert first_job_row.error is None
        assert first_job_row.report is not None
        assert first_job_row.report["documents_ingested"] == 3

        document_count = await session.scalar(select(func.count()).select_from(Document))
        chunk_count = await session.scalar(select(func.count()).select_from(Chunk))
        distinct_hashes = await session.scalar(
            select(func.count(func.distinct(Document.content_sha256)))
        )
        documents = (await session.scalars(select(Document))).all()

        assert document_count == 3
        assert chunk_count == first_report["chunks"]
        assert distinct_hashes == 3
        assert documents

        markdown_document = next(
            document for document in documents if document.filename == "synthetic-lab-procedure.md"
        )
        assert not any(
            document.filename == "synthetic-lab-procedure-copy.md" for document in documents
        )
        assert first_report["duplicates"][0]["filename"] == ("synthetic-lab-procedure-copy.md")
        assert first_report["duplicates"][0]["document_id"] == str(markdown_document.id)

        pdf_document_id = UUID(
            next(
                document["document_id"]
                for document in first_report["documents"]
                if document["filename"] == "synthetic-lab-policy.pdf"
            )
        )
        pdf_chunks = (
            await session.scalars(
                select(Chunk)
                .where(Chunk.document_id == pdf_document_id)
                .order_by(Chunk.chunk_index)
            )
        ).all()
        assert [chunk.page for chunk in pdf_chunks] == [1, 2]

        markdown_chunks = (
            await session.scalars(
                select(Chunk)
                .where(Chunk.document_id == markdown_document.id)
                .order_by(Chunk.chunk_index)
            )
        ).all()
        assert markdown_chunks
        assert all(chunk.page is None for chunk in markdown_chunks)
        assert all(chunk.section_heading for chunk in markdown_chunks)

        vector_norm = np.linalg.norm(np.asarray(pdf_chunks[0].embedding, dtype=np.float32))
        assert vector_norm == pytest.approx(1.0, abs=1e-5)

    second_job = await create_ingestion_job(sessionmaker)
    second_report = await pipeline.run_manifest_job(second_job, manifest_path, sample_dir)

    assert second_report["documents_total"] == 4
    assert second_report["documents_ingested"] == 0
    assert second_report["documents_duplicate"] == 4
    assert second_report["documents_failed"] == 0
    assert second_report["chunks"] == 0
    assert second_report["chunk_length"]["count"] == 0
    assert {row["row"] for row in second_report["rejected_rows"]} == {6, 7, 8}
    assert fake_embedder.calls == 3

    async with sessionmaker() as session:
        second_job_row = await session.get(IngestionJob, second_job)
        assert second_job_row is not None
        assert second_job_row.status == "completed"
        assert second_job_row.report is not None
        assert second_job_row.report["documents_duplicate"] == 4

        assert await session.scalar(select(func.count()).select_from(Document)) == 3
        assert await session.scalar(select(func.count()).select_from(Chunk)) == chunk_count


async def test_bad_document_is_reported_without_crashing_the_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "broken.pdf").write_bytes(b"not a pdf")
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year,version\n"
        "broken.pdf,Broken,Synthetic Agency,guidance,2024,v1\n",
        encoding="utf-8",
    )

    pipeline = IngestionPipeline(sessionmaker, fake_embedder, ingestion_config)
    job_id = await create_ingestion_job(sessionmaker)
    report = await pipeline.run_manifest_job(job_id, manifest_path, documents_dir)

    assert report["documents_total"] == 1
    assert report["documents_ingested"] == 0
    assert report["documents_failed"] == 1
    assert report["chunks"] == 0
    assert report["failures"][0]["filename"] == "broken.pdf"
    assert "PDF" in report["failures"][0]["reason"]
    assert fake_embedder.calls == 0

    async with sessionmaker() as session:
        job = await session.get(IngestionJob, job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.report is not None
        assert job.report["documents_failed"] == 1
        assert await session.scalar(select(func.count()).select_from(Document)) == 0


async def test_manifest_schema_error_marks_job_failed(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year\n"
        "note.txt,Note,Synthetic Agency,guidance,2024\n",
        encoding="utf-8",
    )

    pipeline = IngestionPipeline(sessionmaker, fake_embedder, ingestion_config)
    job_id = await create_ingestion_job(sessionmaker)

    with pytest.raises(IngestionJobError, match="version"):
        await pipeline.run_manifest_job(job_id, manifest_path, documents_dir)

    async with sessionmaker() as session:
        job = await session.get(IngestionJob, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.report is None
        assert job.error is not None
        assert "version" in job.error
        assert job.finished_at is not None


async def test_changed_document_replaces_chunks_and_metadata_only_is_duplicate(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    tmp_path: Path,
) -> None:
    config = IngestionConfig(
        chunk_max_tokens=10,
        chunk_overlap_tokens=2,
        embedding_batch_size=8,
    )
    pipeline = IngestionPipeline(sessionmaker, fake_embedder, config)
    path = tmp_path / "policy.txt"
    path.write_text("alpha " * 80, encoding="utf-8")
    first_metadata = DocumentMetadata(
        filename="policy.txt",
        title="Original title",
        source_agency="Synthetic Agency",
        doc_type="guidance",
        year=2020,
        version="v1",
    )

    first_job = await create_ingestion_job(sessionmaker)
    first_report = await pipeline.run_upload_job(first_job, path, first_metadata)
    assert first_report["documents_ingested"] == 1
    assert first_report["documents_updated"] == 0
    assert first_report["chunks"] > 1
    document_id = UUID(first_report["documents"][0]["document_id"])

    async with sessionmaker() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        original_hash = document.content_sha256
        first_chunks = (
            await session.scalars(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
            )
        ).all()
    first_chunk_ids = {chunk.id for chunk in first_chunks}
    assert len(first_chunks) == first_report["chunks"]

    # A metadata-only change keeps the content/chunks but updates the metadata.
    metadata_only = DocumentMetadata(
        filename="policy.txt",
        title="Metadata-only title",
        source_agency="Synthetic Agency",
        doc_type="regulation",
        year=2024,
        version="v2",
    )
    second_job = await create_ingestion_job(sessionmaker)
    second_report = await pipeline.run_upload_job(second_job, path, metadata_only)
    assert second_report["documents_ingested"] == 0
    assert second_report["documents_updated"] == 0
    assert second_report["documents_duplicate"] == 1
    assert second_report["documents_metadata_updated"] == 1
    assert second_report["metadata_updates"] == [
        {
            "filename": "policy.txt",
            "document_id": str(document_id),
            "changed_fields": ["title", "doc_type", "year", "version"],
        }
    ]
    assert fake_embedder.calls == 1

    async with sessionmaker() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.title == "Metadata-only title"
        assert document.version == "v2"
        assert document.year == 2024
        assert document.doc_type == "regulation"
        assert document.content_sha256 == original_hash
        chunks = (
            await session.scalars(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
            )
        ).all()
    assert {chunk.id for chunk in chunks} == first_chunk_ids

    # Same document identity plus changed content is an update, even when the
    # replacement document is shorter and produces fewer chunks.
    path.write_text("beta " * 5, encoding="utf-8")
    updated_metadata = DocumentMetadata(
        filename="policy.txt",
        title="Updated title",
        source_agency="Synthetic Agency",
        doc_type="guidance",
        year=2025,
        version="v3",
    )
    third_job = await create_ingestion_job(sessionmaker)
    third_report = await pipeline.run_upload_job(third_job, path, updated_metadata)
    assert third_report["documents_ingested"] == 0
    assert third_report["documents_updated"] == 1
    assert third_report["documents_duplicate"] == 0
    assert third_report["chunks"] == 1
    assert third_report["chunks"] < first_report["chunks"]
    assert third_report["updates"][0]["document_id"] == str(document_id)

    async with sessionmaker() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.title == "Updated title"
        assert document.version == "v3"
        assert document.year == 2025
        assert document.content_sha256 != original_hash
        chunks = (
            await session.scalars(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
            )
        ).all()
    assert len(chunks) == third_report["chunks"]
    assert {chunk.id for chunk in chunks}.isdisjoint(first_chunk_ids)
    assert all("beta" in chunk.text for chunk in chunks)


async def test_manifest_metadata_edit_updates_metadata_without_reembedding(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    tmp_path: Path,
) -> None:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "note.txt").write_text("stable content for metadata edit", encoding="utf-8")
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year,version\n"
        "note.txt,Original title,Synthetic Agency,guidance,2020,v1\n",
        encoding="utf-8",
    )
    pipeline = IngestionPipeline(sessionmaker, fake_embedder, ingestion_config)

    first_job = await create_ingestion_job(sessionmaker)
    first_report = await pipeline.run_manifest_job(first_job, manifest_path, documents_dir)
    document_id = UUID(first_report["documents"][0]["document_id"])
    assert fake_embedder.calls == 1

    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year,version\n"
        "note.txt,Manifest is source of truth,Synthetic Agency,regulation,2026,v2\n",
        encoding="utf-8",
    )
    second_job = await create_ingestion_job(sessionmaker)
    second_report = await pipeline.run_manifest_job(second_job, manifest_path, documents_dir)

    assert second_report["documents_duplicate"] == 1
    assert second_report["documents_metadata_updated"] == 1
    assert second_report["metadata_updates"] == [
        {
            "filename": "note.txt",
            "document_id": str(document_id),
            "changed_fields": ["title", "doc_type", "year", "version"],
        }
    ]
    assert fake_embedder.calls == 1

    async with sessionmaker() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.title == "Manifest is source of truth"
        assert document.doc_type == "regulation"
        assert document.year == 2026
        assert document.version == "v2"
        chunk_count = int(
            await session.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
            )
            or 0
        )
    assert chunk_count == first_report["chunks"]


async def test_changed_document_replaces_qdrant_points(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    qdrant_store: QdrantStore,
    tmp_path: Path,
) -> None:
    config = IngestionConfig(
        chunk_max_tokens=10,
        chunk_overlap_tokens=2,
        embedding_batch_size=8,
    )
    pipeline = IngestionPipeline(
        sessionmaker,
        fake_embedder,
        config,
        (qdrant_store,),
    )
    path = tmp_path / "qdrant-update.txt"
    path.write_text("alpha " * 80, encoding="utf-8")
    metadata = DocumentMetadata(
        filename="qdrant-update.txt",
        title="Qdrant update",
        source_agency="Synthetic Agency",
        doc_type="guidance",
        year=2024,
        version="v1",
    )

    first_job = await create_ingestion_job(sessionmaker)
    first_report = await pipeline.run_upload_job(first_job, path, metadata)
    assert first_report["chunks"] > 1
    assert await qdrant_store.count() == first_report["chunks"]
    document_id = UUID(first_report["documents"][0]["document_id"])

    path.write_text("beta " * 5, encoding="utf-8")
    second_job = await create_ingestion_job(sessionmaker)
    second_report = await pipeline.run_upload_job(second_job, path, metadata)
    assert second_report["documents_updated"] == 1
    assert second_report["chunks"] == 1
    assert await qdrant_store.count() == 1

    query_vector = fake_embedder.embed(["beta beta beta beta beta"])[0]
    hits = await qdrant_store.search([float(value) for value in query_vector], top_k=10)
    assert len(hits) == 1
    assert hits[0].document_id == document_id
    assert "beta" in hits[0].text


async def test_metadata_only_update_changes_qdrant_payload_without_reembedding(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    qdrant_store: QdrantStore,
    tmp_path: Path,
) -> None:
    config = IngestionConfig(
        chunk_max_tokens=10,
        chunk_overlap_tokens=2,
        embedding_batch_size=8,
    )
    pipeline = IngestionPipeline(
        sessionmaker,
        fake_embedder,
        config,
        (qdrant_store,),
    )
    path = tmp_path / "metadata.txt"
    path.write_text("metadata payload text " * 20, encoding="utf-8")
    original = DocumentMetadata(
        filename="metadata.txt",
        title="Original metadata",
        source_agency="Synthetic Agency",
        doc_type="guidance",
        year=2020,
        version="v1",
    )
    first_job = await create_ingestion_job(sessionmaker)
    first_report = await pipeline.run_upload_job(first_job, path, original)
    document_id = UUID(first_report["documents"][0]["document_id"])
    assert await qdrant_store.count() == first_report["chunks"]
    assert fake_embedder.calls == 1

    changed = DocumentMetadata(
        filename="metadata.txt",
        title="Changed metadata",
        source_agency="Synthetic Agency",
        doc_type="regulation",
        year=2025,
        version="v2",
    )
    second_job = await create_ingestion_job(sessionmaker)
    second_report = await pipeline.run_upload_job(second_job, path, changed)

    assert second_report["documents_metadata_updated"] == 1
    assert second_report["metadata_updates"][0]["changed_fields"] == [
        "title",
        "doc_type",
        "year",
        "version",
    ]
    assert second_report["chunks"] == 0
    assert fake_embedder.calls == 1
    assert await qdrant_store.count() == first_report["chunks"]

    query = fake_embedder.embed(["metadata payload text"])[0]
    hits = await qdrant_store.search([float(value) for value in query], top_k=50)
    assert len(hits) == first_report["chunks"]
    assert {hit.document_id for hit in hits} == {document_id}
    assert {hit.title for hit in hits} == {"Changed metadata"}
    assert {hit.doc_type for hit in hits} == {"regulation"}
    assert {hit.year for hit in hits} == {2025}
    assert {hit.version for hit in hits} == {"v2"}


class _FlakyQdrantStore:
    """Qdrant wrapper that fails the first fan-out write."""

    name = "qdrant"

    def __init__(self, store: QdrantStore) -> None:
        self.store = store
        self.fail_next_upsert = True

    async def upsert(self, records: object) -> None:
        if self.fail_next_upsert:
            self.fail_next_upsert = False
            raise RuntimeError("injected qdrant failure with secret details")
        await self.store.upsert(records)  # type: ignore[arg-type]

    async def delete_document(self, document_id: UUID) -> int:
        return await self.store.delete_document(document_id)

    async def count(self) -> int:
        return await self.store.count()


async def test_qdrant_fanout_failure_is_safe_and_duplicate_reingest_repairs(
    sessionmaker: async_sessionmaker[AsyncSession],
    fake_embedder: FakeEmbedder,
    ingestion_config: IngestionConfig,
    qdrant_store: QdrantStore,
    tmp_path: Path,
) -> None:
    flaky_store = _FlakyQdrantStore(qdrant_store)
    pipeline = IngestionPipeline(
        sessionmaker,
        fake_embedder,
        ingestion_config,
        (flaky_store,),
    )
    path = tmp_path / "flaky.txt"
    path.write_text(f"fanout failure content {uuid4()}", encoding="utf-8")
    metadata = DocumentMetadata(
        filename="flaky.txt",
        title="Fan-out failure",
        source_agency="Synthetic Agency",
        doc_type="guidance",
        year=2024,
        version="v1",
    )

    failed_job = await create_ingestion_job(sessionmaker)
    with pytest.raises(IngestionJobError, match="Postgres committed"):
        await pipeline.run_upload_job(failed_job, path, metadata)

    async with sessionmaker() as session:
        job = await session.get(IngestionJob, failed_job)
        assert job is not None
        assert job.status == "failed"
        assert job.error is not None
        assert "Postgres committed" in job.error
        assert "out of date" in job.error
        assert "reindex --backend qdrant" in job.error
        assert "injected" not in job.error
        assert "secret" not in job.error
        document_count = await session.scalar(select(func.count()).select_from(Document))
        chunk_count = int(await session.scalar(select(func.count()).select_from(Chunk)) or 0)
    assert document_count == 1
    assert chunk_count > 0
    assert await qdrant_store.count() == 0

    # Re-ingesting the same content repairs the external index without
    # creating a duplicate Postgres document.
    repaired_job = await create_ingestion_job(sessionmaker)
    repaired_report = await pipeline.run_upload_job(repaired_job, path, metadata)
    assert repaired_report["documents_duplicate"] == 1
    assert repaired_report["documents_updated"] == 0
    assert await qdrant_store.count() == chunk_count
