"""Create BH-28 dictionary page range table.

Revision ID: bh28_0011
Revises: bh31_0010
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh28_0011"
down_revision: str | None = "bh31_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the BH-28 dictionary-scoped PDF page-range table."""
    op.create_table(
        "dictionary_page_ranges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("start_page >= 1", name="dictionary_page_range_start_page"),
        sa.CheckConstraint(
            "end_page >= start_page", name="dictionary_page_range_end_page"
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_page_ranges_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_page_ranges")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_page_ranges_dictionary_id"),
        "dictionary_page_ranges",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the BH-28 dictionary-scoped PDF page-range table."""
    op.drop_index(
        op.f("ix_cadmus_dictionary_page_ranges_dictionary_id"),
        table_name="dictionary_page_ranges",
        schema="cadmus",
    )
    op.drop_table("dictionary_page_ranges", schema="cadmus")
