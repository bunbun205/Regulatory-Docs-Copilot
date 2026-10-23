import asyncio
import time
from dataclasses import asdict
from typing import Annotated, Literal, cast

import structlog
from fastapi import APIRouter, Depends, Request

from app.api.deps import require_scope
from app.api.errors import APIError
from app.api.schemas import SearchRequest, SearchResponse, SearchResult
from app.core.security import Scope
from app.store.base import SearchFilters

logger = structlog.get_logger("labdocs.search")

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    request: Request,
    _key: Annotated[object, Depends(require_scope(Scope.READ))],
) -> SearchResponse:
    """Retrieve chunks from a selected vector backend."""
    query = body.query.strip()
    if not query:
        raise APIError(422, "validation_error", "Query must not be blank.")

    stores = getattr(request.app.state, "vector_stores", {})
    backend_value = body.backend or getattr(
        request.app.state,
        "default_vector_backend",
        "pgvector",
    )
    if backend_value not in {"pgvector", "qdrant"}:
        raise APIError(500, "internal_error", "The default vector backend is invalid.")
    backend = cast(Literal["pgvector", "qdrant"], backend_value)
    store = stores.get(backend)
    if store is None:
        raise APIError(
            422,
            "backend_unavailable",
            f"Vector backend {backend!r} is not configured.",
        )

    filter_data = body.filters.model_dump() if body.filters is not None else {}
    filters = SearchFilters(**filter_data)
    try:
        vectors = await asyncio.to_thread(request.app.state.embedder.embed, [query])
    except Exception as exc:
        logger.error("search.embedding_failed", error_type=type(exc).__name__)
        raise APIError(
            503,
            "embedding_unavailable",
            "The query embedding service is unavailable.",
        ) from exc

    if vectors.shape != (1, request.app.state.embedder.dimension):
        raise APIError(
            503,
            "embedding_unavailable",
            "The query embedding service returned an invalid vector.",
        )

    started = time.perf_counter()
    try:
        hits = await store.search(
            [float(value) for value in vectors[0]],
            body.top_k,
            filters,
        )
    except Exception as exc:
        logger.error(
            "search.failed",
            backend=backend,
            error_type=type(exc).__name__,
        )
        raise APIError(
            503,
            "vector_store_unavailable",
            "The selected vector backend is unavailable.",
        ) from exc

    return SearchResponse(
        query=query,
        backend=backend,
        top_k=body.top_k,
        results=[SearchResult(**asdict(hit)) for hit in hits],
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
