import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIMENSION = 384


class ApiKey(Base):
    """A hashed API key with a single scope."""

    __tablename__ = "api_keys"
    __table_args__ = (CheckConstraint("scope IN ('read', 'write')", name="scope"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Document(Base):
    """Metadata for one ingested source document."""

    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("year BETWEEN 1900 AND 2100", name="year_range"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_agency: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(200), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Chunk(Base):
    """A retrievable text chunk with its normalized embedding."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_chunks_document_chunk",
        ),
        CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        CheckConstraint("token_count > 0", name="token_count_positive"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionJob(Base):
    """Status and report for a manifest or upload ingestion run."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
