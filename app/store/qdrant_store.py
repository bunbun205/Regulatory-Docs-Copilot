import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from app.db.models import EMBEDDING_DIMENSION
from app.store.base import SearchFilters, SearchHit, VectorRecord


class QdrantStore:
    """Qdrant-backed vector store with payload metadata for filtering."""

    name = "qdrant"

    def __init__(
        self,
        url: str,
        collection: str,
        *,
        dimension: int = EMBEDDING_DIMENSION,
        api_key: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.collection = collection
        self.dimension = dimension
        self._client = AsyncQdrantClient(
            url=url,
            api_key=api_key or None,
            timeout=timeout,
            prefer_grpc=False,
        )
        self._collection_lock = asyncio.Lock()
        self._collection_ready = False

    async def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        async with self._collection_lock:
            if self._collection_ready:
                return
            if not await self._client.collection_exists(self.collection):
                try:
                    await self._client.create_collection(
                        collection_name=self.collection,
                        vectors_config=VectorParams(
                            size=self.dimension,
                            distance=Distance.COSINE,
                        ),
                    )
                except Exception:
                    # Another process may have created it between the check and
                    # the create. Re-check before treating it as a failure.
                    if not await self._client.collection_exists(self.collection):
                        raise
            info = await self._client.get_collection(self.collection)
            vectors = info.config.params.vectors
            size = getattr(vectors, "size", None)
            if size != self.dimension:
                raise RuntimeError(
                    f"Qdrant collection {self.collection!r} has dimension {size}; "
                    f"expected {self.dimension}."
                )
            self._collection_ready = True

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        await self._ensure_collection()
        points = [
            PointStruct(
                id=str(record.chunk_id),
                vector=list(record.embedding),
                payload={
                    "chunk_id": str(record.chunk_id),
                    "document_id": str(record.document_id),
                    "chunk_index": record.chunk_index,
                    "text": record.text,
                    "token_count": record.token_count,
                    "page": record.page,
                    "section_heading": record.section_heading,
                    "filename": record.filename,
                    "title": record.title,
                    "source_agency": record.source_agency,
                    "doc_type": record.doc_type,
                    "year": record.year,
                    "version": record.version,
                },
            )
            for record in records
        ]
        await self._client.upsert(
            collection_name=self.collection,
            points=points,
            wait=True,
        )

    async def search(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[SearchHit]:
        self._validate_query(vector, top_k)
        await self._ensure_collection()
        response = await self._client.query_points(
            collection_name=self.collection,
            query=list(vector),
            query_filter=self._filter(filters or SearchFilters()),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        hits: list[SearchHit] = []
        for point in response.points:
            payload = point.payload
            if not isinstance(payload, dict):
                raise RuntimeError("Qdrant point is missing its payload.")
            hits.append(
                SearchHit(
                    chunk_id=UUID(str(payload["chunk_id"])),
                    document_id=UUID(str(payload["document_id"])),
                    chunk_index=int(payload["chunk_index"]),
                    text=str(payload["text"]),
                    score=float(point.score),
                    page=payload.get("page"),
                    section_heading=payload.get("section_heading"),
                    filename=str(payload["filename"]),
                    title=str(payload["title"]),
                    source_agency=str(payload["source_agency"]),
                    doc_type=str(payload["doc_type"]),
                    year=int(payload["year"]),
                    version=str(payload["version"]),
                )
            )
        return hits

    async def delete_document(self, document_id: UUID) -> int:
        await self._ensure_collection()
        selector = Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=str(document_id)),
                )
            ]
        )
        count = int(
            (
                await self._client.count(
                    collection_name=self.collection,
                    count_filter=selector,
                    exact=True,
                )
            ).count
        )
        if count:
            await self._client.delete(
                collection_name=self.collection,
                points_selector=FilterSelector(filter=selector),
                wait=True,
            )
        return count

    async def count(self) -> int:
        await self._ensure_collection()
        result = await self._client.count(
            collection_name=self.collection,
            exact=True,
        )
        return int(result.count)

    async def health(self) -> None:
        await self._client.get_collections()

    async def close(self) -> None:
        await self._client.close()

    async def delete_collection(self) -> None:
        """Remove the collection. Used by tests and explicit reindex tooling."""
        await self._client.delete_collection(self.collection)
        self._collection_ready = False

    @staticmethod
    def _filter(filters: SearchFilters) -> Filter | None:
        must: list[Any] = []
        if filters.doc_type is not None:
            must.append(
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value=filters.doc_type),
                )
            )
        if filters.source_agency is not None:
            must.append(
                FieldCondition(
                    key="source_agency",
                    match=MatchValue(value=filters.source_agency),
                )
            )
        if filters.year_min is not None or filters.year_max is not None:
            must.append(
                FieldCondition(
                    key="year",
                    range=Range(
                        gte=filters.year_min,
                        lte=filters.year_max,
                    ),
                )
            )
        return Filter(must=must) if must else None

    def _validate_query(self, vector: Sequence[float], top_k: int) -> None:
        if len(vector) != self.dimension:
            raise ValueError(
                f"Query vector has {len(vector)} dimensions; expected {self.dimension}."
            )
        if top_k <= 0:
            raise ValueError("top_k must be positive")
