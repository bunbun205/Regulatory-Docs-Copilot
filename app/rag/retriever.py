import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import structlog

from app.ingest.embedding import Embedder
from app.store.base import SearchFilters, SearchHit, VectorStore

logger = structlog.get_logger("labdocs.retriever")

Backend = Literal["pgvector", "qdrant"]


class RetrievalError(Exception):
    """Base class for safe retrieval failures."""


class EmbeddingUnavailableError(RetrievalError):
    """The query could not be embedded."""


class VectorStoreUnavailableError(RetrievalError):
    """The selected vector store failed."""


class BackendUnavailableError(RetrievalError):
    """The requested backend is not configured."""


@dataclass(frozen=True)
class RetrievalResult:
    hits: tuple[SearchHit, ...]
    backend: Backend
    latency_ms: float


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        vector_stores: Mapping[str, VectorStore],
        default_backend: Backend,
    ) -> None:
        self.embedder = embedder
        self.vector_stores = vector_stores
        self.default_backend = default_backend

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        filters: SearchFilters | None = None,
        backend: Backend | None = None,
    ) -> RetrievalResult:
        started = time.perf_counter()
        selected = backend or self.default_backend
        store = self.vector_stores.get(selected)
        if store is None:
            raise BackendUnavailableError(f"Vector backend {selected!r} is not configured.")

        try:
            vectors = await asyncio.to_thread(self.embedder.embed, [query])
        except Exception as exc:
            logger.error("retrieval.embedding_failed", error_type=type(exc).__name__)
            raise EmbeddingUnavailableError("The query embedding service is unavailable.") from exc
        if vectors.shape != (1, self.embedder.dimension):
            raise EmbeddingUnavailableError(
                "The query embedding service returned an invalid vector."
            )

        try:
            hits = await store.search(
                [float(value) for value in vectors[0]],
                top_k,
                filters or SearchFilters(),
            )
        except Exception as exc:
            logger.error(
                "retrieval.store_failed",
                backend=selected,
                error_type=type(exc).__name__,
            )
            raise VectorStoreUnavailableError(
                "The selected vector backend is unavailable."
            ) from exc
        return RetrievalResult(
            hits=tuple(hits),
            backend=selected,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
