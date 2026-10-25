from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.store.base import MAX_TOP_K


class WhoAmIResponse(BaseModel):
    name: str = Field(description="Human-readable API key name.")
    scopes: list[str] = Field(description="Effective scopes granted to the key.")


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    title: str
    source_agency: str
    doc_type: str
    year: int
    version: str
    page_count: int | None
    created_at: datetime


class DocumentDetail(DocumentSummary):
    chunk_count: int


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int


class UploadResponse(BaseModel):
    job_id: UUID
    status: Literal["queued"] = "queued"


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    report: dict[str, Any] | None
    error: str | None


class SearchFiltersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: str | None = Field(default=None, min_length=1, max_length=100)
    source_agency: str | None = Field(default=None, min_length=1, max_length=200)
    year_min: int | None = Field(default=None, ge=1900, le=2100)
    year_max: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_year_range(self) -> Self:
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must be less than or equal to year_max")
        return self


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=MAX_TOP_K)
    filters: SearchFiltersRequest | None = None
    backend: Literal["pgvector", "qdrant"] | None = None


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    score: float
    page: int | None
    section_heading: str | None
    filename: str
    title: str
    source_agency: str
    doc_type: str
    year: int
    version: str


class SearchResponse(BaseModel):
    query: str
    backend: Literal["pgvector", "qdrant"]
    top_k: int
    results: list[SearchResult]
    latency_ms: float


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)
    filters: SearchFiltersRequest | None = None
    backend: Literal["pgvector", "qdrant"] | None = None


class AskCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    page: int | None
    snippet: str
    score: float


class AskUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class AskLatency(BaseModel):
    retrieve_ms: float
    generate_ms: float


class AskResponse(BaseModel):
    query: str
    backend: Literal["pgvector", "qdrant"]
    answer: str
    citations: list[AskCitation]
    grounded: bool
    grounding_reason: str | None
    insufficient_evidence: bool
    top_score: float | None
    usage: AskUsage
    latency_ms: AskLatency


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    filters: SearchFiltersRequest | None = None
    backend: Literal["pgvector", "qdrant"] | None = None


class AgentTraceStepResponse(BaseModel):
    step: int
    tool: str
    arguments: dict[str, Any]
    result_summary: str
    latency_ms: float
    error: str | None


class AgentResponse(BaseModel):
    query: str
    backend: Literal["pgvector", "qdrant"]
    answer: str
    citations: list[AskCitation]
    grounded: bool
    grounding_reason: str | None
    trace: list[AgentTraceStepResponse]
    step_count: int
    partial: bool
    partial_reason: str | None
    usage: AskUsage
    latency_ms: float
