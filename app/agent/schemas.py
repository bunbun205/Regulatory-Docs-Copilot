from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentSearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: str | None = Field(default=None, max_length=100)
    source_agency: str | None = Field(default=None, max_length=200)
    year_min: int | None = Field(default=None, ge=1900, le=2100)
    year_max: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_range(self) -> "AgentSearchFilters":
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must be less than or equal to year_max")
        return self


class SearchDocumentsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1000)
    filters: AgentSearchFilters | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class QueryMetadataArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: str | None = Field(default=None, max_length=100)
    source_agency: str | None = Field(default=None, max_length=200)
    year_min: int | None = Field(default=None, ge=1900, le=2100)
    year_max: int | None = Field(default=None, ge=1900, le=2100)
    sort_by: Literal[
        "filename",
        "title",
        "source_agency",
        "doc_type",
        "year",
        "version",
    ] = "filename"
    sort_order: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_range(self) -> "QueryMetadataArgs":
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must be less than or equal to year_max")
        return self
