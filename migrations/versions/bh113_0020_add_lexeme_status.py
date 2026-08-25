"""Add the BH-113 lexeme status column.

Revision ID: bh113_0020
Revises: bh170_0019
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh113_0020"
down_revision: str | None = "bh170_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add lexemes.status (draft/ready_to_process/ready_to_review/complete)."""
    op.add_column(
        "lexemes",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
        schema="cadmus",
    )
    op.create_check_constraint(
        "lexeme_status",
        "lexemes",
        "status IN ('draft', 'ready_to_process', 'ready_to_review', 'complete')",
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop lexemes.status."""
    op.drop_constraint("lexeme_status", "lexemes", schema="cadmus", type_="check")
    op.drop_column("lexemes", "status", schema="cadmus")
