from pathlib import Path
from uuid import UUID

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Chunk, Document, IngestionJob
from app.ingest.pipeline import (
    IngestionConfig,
    IngestionJobError,
    IngestionPipeline,
    create_ingestion_job,
)
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
