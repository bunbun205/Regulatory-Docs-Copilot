from typing import Annotated, Literal, cast

import structlog
from fastapi import APIRouter, Depends, Request

from app.api.deps import require_scope
from app.api.errors import APIError
from app.api.schemas import (
    AskCitation,
    AskLatency,
    AskRequest,
    AskResponse,
    AskUsage,
)
from app.core.config import settings
from app.core.security import Scope
from app.llm.base import LLMError
from app.rag.answerer import Answerer
from app.rag.grounding import citation_snippet
from app.rag.retriever import (
    Backend,
    BackendUnavailableError,
    EmbeddingUnavailableError,
    Retriever,
    VectorStoreUnavailableError,
)
from app.store.base import SearchFilters

logger = structlog.get_logger("labdocs.ask")

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    request: Request,
    _key: Annotated[object, Depends(require_scope(Scope.READ))],
) -> AskResponse:
    """Answer a question with retrieval-grounded citations and abstention."""
    query = body.query.strip()
    if not query:
        raise APIError(422, "validation_error", "Query must not be blank.")

    default_backend = getattr(request.app.state, "default_vector_backend", "pgvector")
    backend_value = body.backend or default_backend
    if backend_value not in {"pgvector", "qdrant"}:
        raise APIError(500, "internal_error", "The default vector backend is invalid.")
    backend = cast(Literal["pgvector", "qdrant"], backend_value)
    stores = getattr(request.app.state, "vector_stores", {})
    if backend not in stores:
        raise APIError(
            422,
            "backend_unavailable",
            f"Vector backend {backend!r} is not configured.",
        )

    filter_data = body.filters.model_dump() if body.filters is not None else {}
    filters = SearchFilters(**filter_data)
    retriever = Retriever(
        request.app.state.embedder,
        stores,
        cast(Backend, default_backend),
    )
    answerer = Answerer(
        retriever,
        request.app.state.llm_client,
        abstention_threshold=settings.ABSTENTION_THRESHOLD,
        top_k=body.top_k or settings.RAG_TOP_K,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    try:
        result = await answerer.answer(query, filters=filters, backend=cast(Backend, backend))
    except BackendUnavailableError as exc:
        raise APIError(422, "backend_unavailable", str(exc)) from exc
    except EmbeddingUnavailableError as exc:
        raise APIError(503, "embedding_unavailable", str(exc)) from exc
    except VectorStoreUnavailableError as exc:
        raise APIError(503, "vector_store_unavailable", str(exc)) from exc
    except LLMError as exc:
        logger.error("ask.llm_failed", error_type=type(exc).__name__)
        raise APIError(
            502,
            "llm_unavailable",
            "The language model is unavailable.",
        ) from exc

    return AskResponse(
        query=query,
        backend=result.backend,
        answer=result.answer,
        citations=[
            AskCitation(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                title=hit.title,
                page=hit.page,
                snippet=citation_snippet(hit.text),
                score=hit.score,
            )
            for hit in result.citations
        ],
        grounded=result.grounded,
        grounding_reason=result.grounding_reason,
        insufficient_evidence=result.insufficient_evidence,
        top_score=result.top_score,
        usage=AskUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
        ),
        latency_ms=AskLatency(
            retrieve_ms=result.retrieve_latency_ms,
            generate_ms=result.generate_latency_ms,
        ),
    )
