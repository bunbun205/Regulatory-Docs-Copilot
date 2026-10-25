from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import EMBEDDING_DIMENSION, Chunk, Document
from app.store.base import MAX_TOP_K, SearchFilters, SearchHit, VectorRecord


class PgVectorStore:
    """pgvector-backed store. The chunk table is the canonical source of truth."""

    name = "pgvector"

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.dimension = dimension

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        async with self.sessionmaker() as session:
            await self._upsert_documents(session, records)
            await self.upsert_chunks(session, records)
            await session.commit()

    async def upsert_chunks(
        self,
        session: AsyncSession,
        records: Sequence[VectorRecord],
    ) -> None:
        """Upsert chunks inside an existing transaction.

        The ingestion pipeline uses this so document metadata and chunks commit
        atomically while still going through the store abstraction.
        """
        if not records:
            return
        statement = pg_insert(Chunk).values(
            [
                {
                    "id": record.chunk_id,
                    "document_id": record.document_id,
                    "chunk_index": record.chunk_index,
                    "text": record.text,
                    "token_count": record.token_count,
                    "page": record.page,
                    "section_heading": record.section_heading,
                    "embedding": list(record.embedding),
                }
                for record in records
            ]
        )
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=[Chunk.id],
            set_={
                "document_id": excluded.document_id,
                "chunk_index": excluded.chunk_index,
                "text": excluded.text,
                "token_count": excluded.token_count,
                "page": excluded.page,
                "section_heading": excluded.section_heading,
                "embedding": excluded.embedding,
            },
        )
        await session.execute(statement)

    async def _upsert_documents(
        self,
        session: AsyncSession,
        records: Sequence[VectorRecord],
    ) -> None:
        documents = {record.document_id: record for record in records}
        statement = pg_insert(Document).values(
            [
                {
                    "id": record.document_id,
                    "filename": record.filename,
                    "title": record.title,
                    "source_agency": record.source_agency,
                    "doc_type": record.doc_type,
                    "year": record.year,
                    "version": record.version,
                    "content_sha256": record.content_sha256,
                    "byte_size": record.byte_size,
                    "page_count": record.page_count,
                }
                for record in documents.values()
            ]
        )
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=[Document.id],
            set_={
                "filename": excluded.filename,
                "title": excluded.title,
                "source_agency": excluded.source_agency,
                "doc_type": excluded.doc_type,
                "year": excluded.year,
                "version": excluded.version,
                "content_sha256": excluded.content_sha256,
                "byte_size": excluded.byte_size,
                "page_count": excluded.page_count,
            },
        )
        await session.execute(statement)

    async def search(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[SearchHit]:
        self._validate_query(vector, top_k)
        filters = filters or SearchFilters()
        conditions = self._conditions(filters)
        distance = Chunk.embedding.cosine_distance(list(vector)).label("distance")
        statement = (
            select(Chunk, Document, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(*conditions)
            .order_by(distance)
            .limit(top_k)
        )
        async with self.sessionmaker() as session:
            if filters.has_filters:
                # HNSW applies SQL filters after the approximate scan, so a
                # selective filter can otherwise return fewer rows than exist.
                await session.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
            rows = (await session.execute(statement)).all()
            if filters.has_filters and len(rows) < top_k:
                matching_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(Chunk)
                        .join(Document, Document.id == Chunk.document_id)
                        .where(*conditions)
                    )
                    or 0
                )
                if matching_count > len(rows):
                    # Last-resort correctness fallback for cases where the
                    # iterative scan still misses matching rows. Force a
                    # sequential scan even if the server/session disabled it.
                    await session.execute(text("SET LOCAL enable_seqscan = on"))
                    await session.execute(text("SET LOCAL enable_indexscan = off"))
                    await session.execute(text("SET LOCAL enable_indexonlyscan = off"))
                    await session.execute(text("SET LOCAL enable_bitmapscan = off"))
                    rows = (await session.execute(statement)).all()
        return [
            SearchHit(
                chunk_id=chunk.id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=1.0 - float(row_distance),
                page=chunk.page,
                section_heading=chunk.section_heading,
                filename=document.filename,
                title=document.title,
                source_agency=document.source_agency,
                doc_type=document.doc_type,
                year=document.year,
                version=document.version,
            )
            for chunk, document, row_distance in rows
        ]

    async def document_ids(self) -> list[UUID]:
        async with self.sessionmaker() as session:
            return list(
                (
                    await session.scalars(
                        select(Document.id).order_by(Document.created_at, Document.id)
                    )
                ).all()
            )

    async def records_for_document(self, document_id: UUID) -> list[VectorRecord]:
        async with self.sessionmaker() as session:
            document = await session.get(Document, document_id)
            if document is None:
                return []
            chunks = (
                await session.scalars(
                    select(Chunk)
                    .where(Chunk.document_id == document_id)
                    .order_by(Chunk.chunk_index)
                )
            ).all()
            return [self._record(document, chunk) for chunk in chunks]

    async def delete_document(self, document_id: UUID) -> int:
        async with self.sessionmaker() as session:
            count = int(
                await session.scalar(
                    select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
                )
                or 0
            )
            await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
            await session.execute(delete(Document).where(Document.id == document_id))
            await session.commit()
        return count

    async def count(self) -> int:
        async with self.sessionmaker() as session:
            return int(await session.scalar(select(func.count()).select_from(Chunk)) or 0)

    @staticmethod
    def _record(document: Document, chunk: Chunk) -> VectorRecord:
        return VectorRecord(
            chunk_id=chunk.id,
            document_id=document.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            token_count=chunk.token_count,
            page=chunk.page,
            section_heading=chunk.section_heading,
            embedding=tuple(float(value) for value in chunk.embedding),
            filename=document.filename,
            title=document.title,
            source_agency=document.source_agency,
            doc_type=document.doc_type,
            year=document.year,
            version=document.version,
            content_sha256=document.content_sha256,
            byte_size=document.byte_size,
            page_count=document.page_count,
        )

    @staticmethod
    def _conditions(filters: SearchFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.doc_type is not None:
            conditions.append(Document.doc_type == filters.doc_type)
        if filters.source_agency is not None:
            conditions.append(Document.source_agency == filters.source_agency)
        if filters.year_min is not None:
            conditions.append(Document.year >= filters.year_min)
        if filters.year_max is not None:
            conditions.append(Document.year <= filters.year_max)
        return conditions

    def _validate_query(self, vector: Sequence[float], top_k: int) -> None:
        if len(vector) != self.dimension:
            raise ValueError(
                f"Query vector has {len(vector)} dimensions; expected {self.dimension}."
            )
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
