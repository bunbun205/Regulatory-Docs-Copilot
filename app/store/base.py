from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

MAX_TOP_K = 50


@dataclass(frozen=True)
class SearchFilters:
    """Filters shared by both vector backends."""

    doc_type: str | None = None
    source_agency: str | None = None
    year_min: int | None = None
    year_max: int | None = None

    def __post_init__(self) -> None:
        if self.year_min is not None and not 1900 <= self.year_min <= 2100:
            raise ValueError("year_min must be between 1900 and 2100")
        if self.year_max is not None and not 1900 <= self.year_max <= 2100:
            raise ValueError("year_max must be between 1900 and 2100")
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must be less than or equal to year_max")

    @property
    def has_filters(self) -> bool:
        return any(
            value is not None
            for value in (
                self.doc_type,
                self.source_agency,
                self.year_min,
                self.year_max,
            )
        )


@dataclass(frozen=True)
class VectorRecord:
    """One chunk with its embedding and the document metadata needed by stores."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    token_count: int
    page: int | None
    section_heading: str | None
    embedding: tuple[float, ...]
    filename: str
    title: str
    source_agency: str
    doc_type: str
    year: int
    version: str
    content_sha256: str
    byte_size: int
    page_count: int | None


@dataclass(frozen=True)
class SearchHit:
    """A single scored retrieval result."""

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


class VectorStore(Protocol):
    """Backend-neutral vector index contract."""

    name: str

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or replace records."""

    async def search(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[SearchHit]:
        """Return the nearest chunks, highest cosine similarity first."""

    async def delete_document(self, document_id: UUID) -> int:
        """Delete all chunks for a document and return the number removed."""

    async def count(self) -> int:
        """Return the number of indexed chunks."""
