"""Add dictionary_settlement_mappings.district (raion short form).

Revision ID: geo_0033
Revises: render_0032
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "geo_0033"
down_revision: str | None = "render_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable district (e.g. "Хот.") column."""
    op.add_column(
        "dictionary_settlement_mappings",
        sa.Column("district", sa.String(length=64), nullable=True),
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the district column."""
    op.drop_column("dictionary_settlement_mappings", "district", schema="cadmus")
