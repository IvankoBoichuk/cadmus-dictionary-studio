"""Link an entry field to the BH-30 settlement mapping it resolves to.

Revision ID: geo_0034
Revises: geo_0033
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "geo_0034"
down_revision: str | None = "geo_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable entry_fields.settlement_mapping_id (FK, ON DELETE SET NULL)."""
    op.add_column(
        "entry_fields",
        sa.Column(
            "settlement_mapping_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "cadmus.dictionary_settlement_mappings.id",
                name=op.f(
                    "fk_entry_fields_settlement_mapping_id_"
                    "dictionary_settlement_mappings"
                ),
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the settlement_mapping_id column."""
    op.drop_column("entry_fields", "settlement_mapping_id", schema="cadmus")
