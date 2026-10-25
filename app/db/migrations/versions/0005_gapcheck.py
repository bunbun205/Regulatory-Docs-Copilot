"""add gap-check jobs and judgement cache

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gapcheck_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("api_key_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="gapcheck_status",
        ),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gapcheck_jobs_status",
        "gapcheck_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_gapcheck_jobs_key_status",
        "gapcheck_jobs",
        ["api_key_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_gapcheck_jobs_active_key",
        "gapcheck_jobs",
        ["api_key_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "gapcheck_judgement_cache",
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("namespace", sa.String(length=200), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key"),
    )


def downgrade() -> None:
    op.drop_table("gapcheck_judgement_cache")
    op.drop_index("uq_gapcheck_jobs_active_key", table_name="gapcheck_jobs")
    op.drop_index("ix_gapcheck_jobs_key_status", table_name="gapcheck_jobs")
    op.drop_index("ix_gapcheck_jobs_status", table_name="gapcheck_jobs")
    op.drop_table("gapcheck_jobs")
