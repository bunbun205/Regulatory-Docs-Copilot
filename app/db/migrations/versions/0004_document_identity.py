"""add stable document identity for re-ingestion

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_agency_filename",
        "documents",
        ["source_agency", "filename"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_documents_agency_filename",
        "documents",
        type_="unique",
    )
