import json
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.schemas import AgentSearchFilters, QueryMetadataArgs, SearchDocumentsArgs
from app.db.models import Document
from app.llm.base import ToolDefinition
from app.rag.retriever import Backend, Retriever
from app.store.base import SearchFilters, SearchHit

logger = structlog.get_logger("labdocs.agent.tools")

SEARCH_DOCUMENTS_TOOL = ToolDefinition(
    name="search_documents",
    description=(
        "Search the ingested regulatory corpus for text chunks. Use this for "
        "questions about what a document says. Returns chunk ids, titles, pages, "
        "scores and short text excerpts."
    ),
    parameters=SearchDocumentsArgs.model_json_schema(),
)
QUERY_METADATA_TOOL = ToolDefinition(
    name="query_metadata",
    description=(
        "Query structured document metadata (filename, title, agency, doc_type, "
        "year, version) with validated filters and sorting. Use this to find or "
        "compare documents before searching their contents."
    ),
    parameters=QueryMetadataArgs.model_json_schema(),
)
TOOL_DEFINITIONS = (SEARCH_DOCUMENTS_TOOL, QUERY_METADATA_TOOL)


@dataclass(frozen=True)
class ToolResult:
    content: str
    summary: str
    hits: tuple[SearchHit, ...] = ()
    documents: tuple[dict[str, Any], ...] = ()
    validated_arguments: dict[str, Any] | None = None
    truncated: bool = False
    error: str | None = None


class AgentTools:
    def __init__(
        self,
        retriever: Retriever,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        max_output_chars: int = 8000,
        max_metadata_rows: int = 50,
    ) -> None:
        self.retriever = retriever
        self.sessionmaker = sessionmaker
        self.max_output_chars = max_output_chars
        self.max_metadata_rows = max_metadata_rows

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        base_filters: SearchFilters,
        backend: Backend,
    ) -> ToolResult:
        if name == "search_documents":
            return await self._search(arguments, base_filters=base_filters, backend=backend)
        if name == "query_metadata":
            return await self._metadata(arguments, base_filters=base_filters)
        return ToolResult(
            content=json.dumps({"error": "unknown_tool", "tool": name}),
            summary=f"Unknown tool {name!r}.",
            error="unknown_tool",
        )

    async def _search(
        self,
        arguments: dict[str, Any],
        *,
        base_filters: SearchFilters,
        backend: Backend,
    ) -> ToolResult:
        try:
            args = SearchDocumentsArgs.model_validate(arguments)
        except ValidationError as exc:
            return _argument_error("search_documents", exc)
        filters = _merge_filters(base_filters, args.filters)
        try:
            result = await self.retriever.retrieve(
                args.query,
                top_k=args.top_k,
                filters=filters,
                backend=backend,
            )
        except Exception as exc:
            logger.error(
                "agent.search_tool_failed",
                error_type=type(exc).__name__,
            )
            return ToolResult(
                content=json.dumps({"error": "search_failed"}),
                summary="search_documents failed.",
                error="search_failed",
            )

        payload = {
            "count": len(result.hits),
            "results": [
                {
                    "chunk_id": str(hit.chunk_id),
                    "document_id": str(hit.document_id),
                    "title": hit.title,
                    "filename": hit.filename,
                    "page": hit.page,
                    "section_heading": hit.section_heading,
                    "score": round(hit.score, 6),
                    "text": hit.text[:800],
                }
                for hit in result.hits
            ],
        }
        content, truncated = self._serialise(payload)
        top = result.hits[0].score if result.hits else None
        summary = f"search_documents returned {len(result.hits)} chunks" + (
            f"; top score {top:.4f}" if top is not None else ""
        )
        if truncated:
            summary += "; output truncated"
        return ToolResult(
            content=content,
            summary=summary,
            hits=tuple(result.hits),
            validated_arguments=args.model_dump(),
            truncated=truncated,
        )

    async def _metadata(
        self,
        arguments: dict[str, Any],
        *,
        base_filters: SearchFilters,
    ) -> ToolResult:
        try:
            args = QueryMetadataArgs.model_validate(arguments)
        except ValidationError as exc:
            return _argument_error("query_metadata", exc)

        doc_type = args.doc_type or base_filters.doc_type
        source_agency = args.source_agency or base_filters.source_agency
        year_min = args.year_min if args.year_min is not None else base_filters.year_min
        year_max = args.year_max if args.year_max is not None else base_filters.year_max
        if year_min is not None and year_max is not None and year_min > year_max:
            return ToolResult(
                content=json.dumps({"error": "invalid_arguments", "detail": "invalid year range"}),
                summary="query_metadata rejected an invalid year range.",
                error="invalid_arguments",
            )

        async with self.sessionmaker() as session:
            documents = (await session.scalars(select(Document))).all()

        rows = [
            {
                "document_id": str(document.id),
                "filename": document.filename,
                "title": document.title,
                "source_agency": document.source_agency,
                "doc_type": document.doc_type,
                "year": document.year,
                "version": document.version,
            }
            for document in documents
        ]
        frame = pd.DataFrame(rows)
        if frame.empty:
            records: list[dict[str, Any]] = []
        else:
            if doc_type is not None:
                frame = frame[frame["doc_type"] == doc_type]
            if source_agency is not None:
                frame = frame[frame["source_agency"] == source_agency]
            if year_min is not None:
                frame = frame[frame["year"] >= year_min]
            if year_max is not None:
                frame = frame[frame["year"] <= year_max]
            frame = frame.sort_values(
                by=args.sort_by,
                ascending=args.sort_order == "asc",
                kind="stable",
            ).head(min(args.limit, self.max_metadata_rows))
            records = cast(list[dict[str, Any]], frame.to_dict(orient="records"))

        payload = {"count": len(records), "documents": records}
        content, truncated = self._serialise(payload)
        summary = f"query_metadata returned {len(records)} documents"
        if truncated:
            summary += "; output truncated"
        return ToolResult(
            content=content,
            summary=summary,
            documents=tuple(records),
            validated_arguments=args.model_dump(),
            truncated=truncated,
        )

    def _serialise(self, payload: dict[str, Any]) -> tuple[str, bool]:
        content = json.dumps(payload, ensure_ascii=False, default=str)
        if len(content) <= self.max_output_chars:
            return content, False
        return content[: self.max_output_chars] + "...[truncated]", True


def _merge_filters(
    base: SearchFilters,
    tool_filters: AgentSearchFilters | None,
) -> SearchFilters:
    if tool_filters is None:
        return base
    return SearchFilters(
        doc_type=tool_filters.doc_type or base.doc_type,
        source_agency=tool_filters.source_agency or base.source_agency,
        year_min=tool_filters.year_min if tool_filters.year_min is not None else base.year_min,
        year_max=tool_filters.year_max if tool_filters.year_max is not None else base.year_max,
    )


def _argument_error(tool: str, exc: ValidationError) -> ToolResult:
    errors = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors(include_input=False, include_url=False)
    ]
    return ToolResult(
        content=json.dumps({"error": "invalid_arguments", "tool": tool, "details": errors}),
        summary=f"{tool} rejected invalid arguments.",
        error="invalid_arguments",
    )
