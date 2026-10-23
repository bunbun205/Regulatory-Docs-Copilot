from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
