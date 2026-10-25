import asyncio
import hashlib
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Chunk, Document, IngestionJob
from app.ingest.chunk import ChunkDraft, make_chunks
from app.ingest.embedding import Embedder, normalize_rows
from app.ingest.extract import ExtractedDocument, ExtractionError, extract_document
from app.ingest.manifest import ManifestError, ManifestRow, load_manifest
from app.ingest.report import build_report
from app.store.base import VectorRecord, VectorStore
from app.store.pgvector_store import PgVectorStore

logger = structlog.get_logger("labdocs.ingest")


class IngestionError(Exception):
    """A safe, user-visible ingestion failure."""


class IngestionJobError(IngestionError):
    """An ingestion job could not be run or completed."""


@dataclass(frozen=True)
class IngestionConfig:
    chunk_max_tokens: int = 500
    chunk_overlap_tokens: int = 80
    embedding_batch_size: int = 32
    max_file_bytes: int = 25 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.chunk_max_tokens <= 0:
            raise ValueError("chunk_max_tokens must be positive")
        if not 0 <= self.chunk_overlap_tokens < self.chunk_max_tokens:
            raise ValueError("chunk_overlap_tokens must be less than chunk_max_tokens")
        if self.embedding_batch_size <= 0:
            raise ValueError("embedding_batch_size must be positive")
        if self.max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")


@dataclass(frozen=True)
class DocumentMetadata:
    filename: str
    title: str
    source_agency: str
    doc_type: str
    year: int
    version: str


@dataclass(frozen=True)
class _DocumentOutcome:
    duplicate: bool
    updated: bool
    document_id: uuid.UUID | None
    chunk_count: int
    token_counts: tuple[int, ...]
    page_count: int | None
    metadata_updated: tuple[str, ...] = ()


async def create_ingestion_job(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    job_id = uuid.uuid4()
    async with sessionmaker() as session:
        session.add(IngestionJob(id=job_id, status="queued"))
        await session.commit()
    return job_id


class IngestionPipeline:
    """Manifest/upload ingestion with content-hash idempotency."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        embedder: Embedder,
        config: IngestionConfig,
        vector_stores: Sequence[VectorStore] = (),
    ) -> None:
        self.sessionmaker = sessionmaker
        self.embedder = embedder
        self.config = config
        self.pg_store = PgVectorStore(sessionmaker)
        self.vector_stores = tuple(vector_stores)

    async def run_manifest_job(
        self,
        job_id: uuid.UUID,
        manifest_path: Path,
        documents_dir: Path,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        await self._mark_running(job_id)

        try:
            manifest = load_manifest(manifest_path, documents_dir)
        except ManifestError as exc:
            await self._mark_failed(job_id, str(exc))
            logger.warning(
                "ingestion.manifest_rejected",
                job_id=str(job_id),
                reason=str(exc),
            )
            raise IngestionJobError(str(exc)) from exc
        except Exception as exc:
            logger.error(
                "ingestion.manifest_crashed",
                job_id=str(job_id),
                error_type=type(exc).__name__,
            )
            await self._mark_failed(job_id, "Manifest could not be read.")
            raise

        logger.info(
            "ingestion.manifest_loaded",
            job_id=str(job_id),
            valid_rows=len(manifest.rows),
            rejected_rows=len(manifest.rejected_rows),
        )

        documents: list[dict[str, Any]] = []
        updates: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        metadata_updates: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        token_counts: list[int] = []

        for row in manifest.rows:
            try:
                outcome = await self._ingest_file(row.path, _metadata_from_row(row))
            except (IngestionError, ExtractionError, OSError) as exc:
                reason = _failure_reason(exc)
                failures.append({"filename": row.filename, "reason": reason})
                logger.warning(
                    "ingestion.document_failed",
                    job_id=str(job_id),
                    filename=row.filename,
                    reason=reason,
                )
                continue
            except Exception as exc:
                logger.error(
                    "ingestion.document_crashed",
                    job_id=str(job_id),
                    filename=row.filename,
                    error_type=type(exc).__name__,
                )
                await self._mark_failed(
                    job_id,
                    "Ingestion failed while processing a document.",
                )
                raise

            if outcome.metadata_updated:
                metadata_updates.append(
                    {
                        "filename": row.filename,
                        "document_id": (
                            str(outcome.document_id) if outcome.document_id is not None else None
                        ),
                        "changed_fields": list(outcome.metadata_updated),
                    }
                )
            if outcome.duplicate:
                duplicates.append(
                    {
                        "filename": row.filename,
                        "document_id": (
                            str(outcome.document_id) if outcome.document_id is not None else None
                        ),
                        "metadata_updated": list(outcome.metadata_updated),
                    }
                )
            else:
                entry = {
                    "document_id": str(outcome.document_id),
                    "filename": row.filename,
                    "chunks": outcome.chunk_count,
                    "page_count": outcome.page_count,
                }
                if outcome.updated:
                    updates.append(entry)
                else:
                    documents.append(entry)
                token_counts.extend(outcome.token_counts)

        report = build_report(
            documents_total=len(manifest.rows),
            documents=documents,
            updates=updates,
            duplicates=duplicates,
            metadata_updates=metadata_updates,
            failures=failures,
            rejected_rows=[
                {
                    "row": rejected.row_number,
                    "filename": rejected.filename,
                    "reasons": list(rejected.reasons),
                }
                for rejected in manifest.rejected_rows
            ],
            token_counts=token_counts,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        await self._mark_completed(job_id, report)
        logger.info(
            "ingestion.completed",
            job_id=str(job_id),
            documents=len(documents),
            updates=len(updates),
            duplicates=len(duplicates),
            failures=len(failures),
            rejected=len(manifest.rejected_rows),
            chunks=int(report["chunks"]),
        )
        return report

    async def run_upload_job(
        self,
        job_id: uuid.UUID,
        path: Path,
        metadata: DocumentMetadata,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        await self._mark_running(job_id)

        try:
            outcome = await self._ingest_file(path, metadata)
        except (IngestionError, ExtractionError, OSError) as exc:
            reason = _failure_reason(exc)
            await self._mark_failed(job_id, reason)
            logger.warning(
                "ingestion.upload_failed",
                job_id=str(job_id),
                reason=reason,
            )
            raise IngestionJobError(reason) from exc
        except Exception as exc:
            logger.error(
                "ingestion.upload_crashed",
                job_id=str(job_id),
                error_type=type(exc).__name__,
            )
            await self._mark_failed(job_id, "Ingestion failed.")
            raise

        documents: list[dict[str, Any]] = []
        updates: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        metadata_updates: list[dict[str, Any]] = []
        token_counts: list[int] = []
        if outcome.metadata_updated:
            metadata_updates.append(
                {
                    "filename": metadata.filename,
                    "document_id": (
                        str(outcome.document_id) if outcome.document_id is not None else None
                    ),
                    "changed_fields": list(outcome.metadata_updated),
                }
            )
        if outcome.duplicate:
            duplicates.append(
                {
                    "filename": metadata.filename,
                    "document_id": (
                        str(outcome.document_id) if outcome.document_id is not None else None
                    ),
                    "metadata_updated": list(outcome.metadata_updated),
                }
            )
        else:
            entry = {
                "document_id": str(outcome.document_id),
                "filename": metadata.filename,
                "chunks": outcome.chunk_count,
                "page_count": outcome.page_count,
            }
            if outcome.updated:
                updates.append(entry)
            else:
                documents.append(entry)
            token_counts.extend(outcome.token_counts)

        report = build_report(
            documents_total=1,
            documents=documents,
            updates=updates,
            duplicates=duplicates,
            metadata_updates=metadata_updates,
            failures=[],
            rejected_rows=[],
            token_counts=token_counts,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        await self._mark_completed(job_id, report)
        logger.info(
            "ingestion.upload_completed",
            job_id=str(job_id),
            duplicate=outcome.duplicate,
            updated=outcome.updated,
            chunks=int(report["chunks"]),
        )
        return report

    async def _ingest_file(
        self,
        path: Path,
        metadata: DocumentMetadata,
    ) -> _DocumentOutcome:
        try:
            byte_size = path.stat().st_size
        except OSError as exc:
            raise IngestionError("File could not be read.") from exc
        if byte_size == 0:
            raise IngestionError("File is empty.")
        if byte_size > self.config.max_file_bytes:
            raise IngestionError("File exceeds the maximum allowed size.")

        try:
            data = await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            raise IngestionError("File could not be read.") from exc

        content_hash = hashlib.sha256(data).hexdigest()
        existing = await self._find_document_by_hash(content_hash)
        if existing is not None:
            metadata_updated: tuple[str, ...] = ()
            if (
                existing.source_agency == metadata.source_agency
                and existing.filename == metadata.filename
            ):
                metadata_updated = await self._update_metadata_only(existing.id, metadata)
                if metadata_updated:
                    await self._update_external_metadata(existing.id, metadata)
            if not metadata_updated:
                await self._sync_external_stores(existing.id)
            return _DocumentOutcome(
                duplicate=True,
                updated=False,
                document_id=existing.id,
                chunk_count=0,
                token_counts=(),
                page_count=None,
                metadata_updated=metadata_updated,
            )

        existing_id = await self._find_document_id_by_identity(metadata)
        try:
            extracted, drafts = await asyncio.to_thread(self._extract_and_chunk, path)
        except ExtractionError:
            raise
        except OSError as exc:
            raise IngestionError("File could not be read.") from exc

        if not drafts:
            raise IngestionError("Document contains no extractable text.")

        try:
            vectors = await asyncio.to_thread(
                self.embedder.embed,
                [draft.text for draft in drafts],
            )
            vectors = normalize_rows(vectors)
        except Exception as exc:
            logger.error(
                "ingestion.embedding_failed",
                filename=metadata.filename,
                error_type=type(exc).__name__,
            )
            raise IngestionError("Embedding failed.") from exc

        if vectors.shape != (len(drafts), self.embedder.dimension):
            raise IngestionError("Embedding dimension mismatch.")

        document_id = existing_id or uuid.uuid4()
        records = [
            VectorRecord(
                chunk_id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=index,
                text=draft.text,
                token_count=draft.token_count,
                page=draft.page,
                section_heading=draft.section_heading,
                embedding=tuple(float(value) for value in vectors[index]),
                filename=metadata.filename,
                title=metadata.title,
                source_agency=metadata.source_agency,
                doc_type=metadata.doc_type,
                year=metadata.year,
                version=metadata.version,
                content_sha256=content_hash,
                byte_size=byte_size,
                page_count=extracted.page_count,
            )
            for index, draft in enumerate(drafts)
        ]

        if existing_id is not None:
            updated = await self._update_existing_document(
                document_id=existing_id,
                metadata=metadata,
                content_hash=content_hash,
                byte_size=byte_size,
                page_count=extracted.page_count,
                records=records,
            )
            if not updated:
                await self._sync_external_stores(existing_id)
                return _DocumentOutcome(
                    duplicate=True,
                    updated=False,
                    document_id=existing_id,
                    chunk_count=0,
                    token_counts=(),
                    page_count=None,
                )
            await self._replace_external_stores(records)
            return _DocumentOutcome(
                duplicate=False,
                updated=True,
                document_id=existing_id,
                chunk_count=len(drafts),
                token_counts=tuple(draft.token_count for draft in drafts),
                page_count=extracted.page_count,
            )

        try:
            async with self.sessionmaker() as session:
                insert_document = (
                    pg_insert(Document)
                    .values(
                        id=document_id,
                        filename=metadata.filename,
                        title=metadata.title,
                        source_agency=metadata.source_agency,
                        doc_type=metadata.doc_type,
                        year=metadata.year,
                        version=metadata.version,
                        content_sha256=content_hash,
                        byte_size=byte_size,
                        page_count=extracted.page_count,
                    )
                    .on_conflict_do_nothing(index_elements=[Document.content_sha256])
                    .returning(Document.id)
                )
                inserted_id = await session.scalar(insert_document)
                if inserted_id is None:
                    existing_id = await session.scalar(
                        select(Document.id).where(Document.content_sha256 == content_hash)
                    )
                    await session.rollback()
                    if existing_id is not None:
                        await self._sync_external_stores(existing_id)
                    return _DocumentOutcome(
                        duplicate=True,
                        updated=False,
                        document_id=existing_id,
                        chunk_count=0,
                        token_counts=(),
                        page_count=None,
                    )

                await self.pg_store.upsert_chunks(session, records)
                await session.commit()
        except IntegrityError as exc:
            logger.warning(
                "ingestion.identity_conflict",
                filename=metadata.filename,
                source_agency=metadata.source_agency,
            )
            raise IngestionError("Document changed during ingestion; retry ingestion.") from exc

        await self._write_external_stores(records)
        return _DocumentOutcome(
            duplicate=False,
            updated=False,
            document_id=document_id,
            chunk_count=len(drafts),
            token_counts=tuple(draft.token_count for draft in drafts),
            page_count=extracted.page_count,
        )

    async def _update_existing_document(
        self,
        *,
        document_id: uuid.UUID,
        metadata: DocumentMetadata,
        content_hash: str,
        byte_size: int,
        page_count: int | None,
        records: Sequence[VectorRecord],
    ) -> bool:
        """Replace an existing document's chunks in one transaction."""
        async with self.sessionmaker() as session:
            current_hash = await session.scalar(
                select(Document.content_sha256).where(Document.id == document_id).with_for_update()
            )
            if current_hash is None:
                raise IngestionError("Document changed during ingestion; retry ingestion.")
            if current_hash == content_hash:
                return False
            conflicting_id = await session.scalar(
                select(Document.id).where(
                    Document.content_sha256 == content_hash,
                    Document.id != document_id,
                )
            )
            if conflicting_id is not None:
                raise IngestionError("Document content matches another document; retry ingestion.")

            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    filename=metadata.filename,
                    title=metadata.title,
                    source_agency=metadata.source_agency,
                    doc_type=metadata.doc_type,
                    year=metadata.year,
                    version=metadata.version,
                    content_sha256=content_hash,
                    byte_size=byte_size,
                    page_count=page_count,
                )
            )
            await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
            await self.pg_store.upsert_chunks(session, records)
            await session.commit()
        return True

    async def _sync_external_stores(self, document_id: uuid.UUID) -> None:
        if not self.vector_stores:
            return
        records = await self.pg_store.records_for_document(document_id)
        if not records:
            raise IngestionError("Document has no chunks to index.")
        await self._replace_external_stores(records)

    async def _update_metadata_only(
        self,
        document_id: uuid.UUID,
        metadata: DocumentMetadata,
    ) -> tuple[str, ...]:
        """Update document metadata in Postgres and report changed fields."""
        async with self.sessionmaker() as session:
            document = await session.scalar(
                select(Document).where(Document.id == document_id).with_for_update()
            )
            if document is None:
                raise IngestionError("Document changed during ingestion; retry ingestion.")
            changed = tuple(
                field
                for field in ("title", "doc_type", "year", "version")
                if getattr(document, field) != getattr(metadata, field)
            )
            if not changed:
                return ()
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    filename=metadata.filename,
                    title=metadata.title,
                    source_agency=metadata.source_agency,
                    doc_type=metadata.doc_type,
                    year=metadata.year,
                    version=metadata.version,
                )
            )
            await session.commit()
        logger.info(
            "ingestion.metadata_updated",
            document_id=str(document_id),
            changed_fields=list(changed),
        )
        return changed

    async def _update_external_metadata(
        self,
        document_id: uuid.UUID,
        metadata: DocumentMetadata,
    ) -> None:
        if not self.vector_stores:
            return
        for store in self.vector_stores:
            try:
                await store.update_document_metadata(
                    document_id,
                    filename=metadata.filename,
                    title=metadata.title,
                    source_agency=metadata.source_agency,
                    doc_type=metadata.doc_type,
                    year=metadata.year,
                    version=metadata.version,
                )
            except Exception as exc:
                logger.error(
                    "ingestion.vector_store_metadata_failed",
                    store=store.name,
                    document_id=str(document_id),
                    error_type=type(exc).__name__,
                )
                raise IngestionError(_external_sync_failure_message(store.name)) from exc

    async def _write_external_stores(self, records: Sequence[VectorRecord]) -> None:
        if not self.vector_stores or not records:
            return
        for store in self.vector_stores:
            try:
                await store.upsert(records)
            except Exception as exc:
                logger.error(
                    "ingestion.vector_store_failed",
                    store=store.name,
                    document_id=str(records[0].document_id),
                    error_type=type(exc).__name__,
                )
                raise IngestionError(_external_sync_failure_message(store.name)) from exc

    async def _replace_external_stores(self, records: Sequence[VectorRecord]) -> None:
        if not self.vector_stores or not records:
            return
        for store in self.vector_stores:
            try:
                await store.delete_document(records[0].document_id)
                await store.upsert(records)
            except Exception as exc:
                logger.error(
                    "ingestion.vector_store_replace_failed",
                    store=store.name,
                    document_id=str(records[0].document_id),
                    error_type=type(exc).__name__,
                )
                raise IngestionError(_external_sync_failure_message(store.name)) from exc

    def _extract_and_chunk(self, path: Path) -> tuple[ExtractedDocument, list[ChunkDraft]]:
        extracted = extract_document(path)
        drafts = make_chunks(
            extracted.blocks,
            max_tokens=self.config.chunk_max_tokens,
            overlap_tokens=self.config.chunk_overlap_tokens,
        )
        return extracted, drafts

    async def _find_document_by_hash(self, content_hash: str) -> Document | None:
        async with self.sessionmaker() as session:
            return await session.scalar(
                select(Document).where(Document.content_sha256 == content_hash)
            )

    async def _find_document_id_by_identity(
        self,
        metadata: DocumentMetadata,
    ) -> uuid.UUID | None:
        async with self.sessionmaker() as session:
            return await session.scalar(
                select(Document.id).where(
                    Document.source_agency == metadata.source_agency,
                    Document.filename == metadata.filename,
                )
            )

    async def _mark_running(self, job_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        async with self.sessionmaker() as session:
            updated_id = await session.scalar(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(
                    status="running",
                    started_at=now,
                    finished_at=None,
                    error=None,
                )
                .returning(IngestionJob.id)
            )
            if updated_id is None:
                raise IngestionJobError("Ingestion job was not found.")
            await session.commit()

    async def _mark_completed(
        self,
        job_id: uuid.UUID,
        report: dict[str, Any],
    ) -> None:
        async with self.sessionmaker() as session:
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(
                    status="completed",
                    report=report,
                    error=None,
                    finished_at=datetime.now(UTC),
                )
            )
            await session.commit()

    async def _mark_failed(self, job_id: uuid.UUID, error: str) -> None:
        async with self.sessionmaker() as session:
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(
                    status="failed",
                    error=error[:1000],
                    finished_at=datetime.now(UTC),
                )
            )
            await session.commit()


async def run_upload_job_background(
    sessionmaker: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    config: IngestionConfig,
    job_id: uuid.UUID,
    path: Path,
    metadata: DocumentMetadata,
    vector_stores: Sequence[VectorStore] = (),
) -> None:
    """Run an upload ingestion as a FastAPI background task without raising."""
    pipeline = IngestionPipeline(sessionmaker, embedder, config, vector_stores)
    try:
        await pipeline.run_upload_job(job_id, path, metadata)
    except Exception as exc:
        logger.error(
            "ingestion.background_failed",
            job_id=str(job_id),
            error_type=type(exc).__name__,
        )


def _metadata_from_row(row: ManifestRow) -> DocumentMetadata:
    return DocumentMetadata(
        filename=row.filename,
        title=row.title,
        source_agency=row.source_agency,
        doc_type=row.doc_type,
        year=row.year,
        version=row.version,
    )


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, (IngestionError, ExtractionError)):
        return str(exc)
    if isinstance(exc, OSError):
        return "File could not be read."
    return "Document could not be processed."


def _external_sync_failure_message(store_name: str) -> str:
    return (
        f"Postgres committed this document, but the {store_name} index is out of date. "
        f"Run `python -m app.cli reindex --backend {store_name}` to rebuild it."
    )
