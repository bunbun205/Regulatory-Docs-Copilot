from typing import Annotated, Literal, cast

import structlog
from fastapi import APIRouter, Depends, Request

from app.agent.loop import AgentLoop
from app.agent.tools import AgentTools
from app.api.deps import require_scope
from app.api.errors import APIError
from app.api.schemas import (
    AgentRequest,
    AgentResponse,
    AgentTraceStepResponse,
    AskCitation,
    AskUsage,
)
from app.core.config import settings
from app.core.security import Scope
from app.llm.base import LLMError
from app.rag.grounding import citation_snippet
from app.rag.retriever import Backend, Retriever
from app.store.base import SearchFilters

logger = structlog.get_logger("labdocs.agent.api")

router = APIRouter(tags=["agent"])


@router.post("/agent/run", response_model=AgentResponse)
async def run_agent(
    body: AgentRequest,
    request: Request,
    _key: Annotated[object, Depends(require_scope(Scope.READ))],
) -> AgentResponse:
    """Run the bounded tool-using agent and return its full trace."""
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
    tools = AgentTools(
        retriever,
        request.app.state.sessionmaker,
        max_output_chars=settings.AGENT_MAX_TOOL_OUTPUT_CHARS,
        max_metadata_rows=settings.AGENT_MAX_METADATA_ROWS,
    )
    loop = AgentLoop(
        request.app.state.llm_client,
        tools,
        max_steps=settings.AGENT_MAX_STEPS,
        step_timeout_seconds=settings.AGENT_STEP_TIMEOUT_SECONDS,
        total_timeout_seconds=settings.AGENT_TOTAL_TIMEOUT_SECONDS,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    try:
        result = await loop.run(
            query,
            filters=filters,
            backend=cast(Backend, backend),
        )
    except LLMError as exc:
        logger.error("agent.llm_failed", error_type=type(exc).__name__)
        raise APIError(
            502,
            "llm_unavailable",
            "The language model is unavailable.",
        ) from exc

    return AgentResponse(
        query=query,
        backend=backend,
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
        trace=[
            AgentTraceStepResponse(
                step=step.step,
                tool=step.tool,
                arguments=step.arguments,
                result_summary=step.result_summary,
                latency_ms=step.latency_ms,
                error=step.error,
            )
            for step in result.trace
        ],
        step_count=result.step_count,
        partial=result.partial,
        partial_reason=result.partial_reason,
        usage=AskUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
        ),
        latency_ms=result.latency_ms,
    )
