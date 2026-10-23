"""ingestion tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_agency", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=200), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("year BETWEEN 1900 AND 2100", name=op.f("ck_documents_year_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("content_sha256", name=op.f("uq_documents_content_sha256")),
    )
    op.create_index(op.f("ix_documents_doc_type"), "documents", ["doc_type"])
    op.create_index(op.f("ix_documents_source_agency"), "documents", ["source_agency"])
    op.create_index(op.f("ix_documents_year"), "documents", ["year"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(dim=384), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("chunk_index >= 0", name=op.f("ck_chunks_chunk_index_nonnegative")),
        sa.CheckConstraint("token_count > 0", name=op.f("ck_chunks_token_count_positive")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
        sa.UniqueConstraint("document_id", "chunk_index", name=op.f("uq_chunks_document_chunk")),
    )
    op.create_index(op.f("ix_chunks_document_id"), "chunks", ["document_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name=op.f("ck_ingestion_jobs_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_jobs")),
    )
    op.create_index(op.f("ix_ingestion_jobs_status"), "ingestion_jobs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_jobs_status"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index(op.f("ix_chunks_document_id"), table_name="chunks")
    op.drop_table("chunks")
    op.drop_index(op.f("ix_documents_year"), table_name="documents")
    op.drop_index(op.f("ix_documents_source_agency"), table_name="documents")
    op.drop_index(op.f("ix_documents_doc_type"), table_name="documents")
    op.drop_table("documents")
