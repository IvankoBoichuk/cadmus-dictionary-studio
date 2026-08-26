"""Create entry_fragments for BH-148 (ADR-0006 EntryFragment).

Revision ID: bh148_0024
Revises: bh148_0023
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh148_0024"
down_revision: str | None = "bh148_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the entry_fragments table: one entry's location on one page."""
    op.create_table(
        "entry_fragments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("x2", sa.Float(), nullable=True),
        sa.Column("y2", sa.Float(), nullable=True),
        sa.Column("width2", sa.Float(), nullable=True),
        sa.Column("height2", sa.Float(), nullable=True),
        sa.Column("reading_order", sa.Integer(), nullable=False),
        sa.Column("recognized_text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="entry_fragment_positive_size"
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["cadmus.dictionary_entries.id"],
            name=op.f("fk_entry_fragments_entry_id_dictionary_entries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["cadmus.dictionary_pages.id"],
            name=op.f("fk_entry_fragments_page_id_dictionary_pages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_fragments")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_entry_fragments_entry_id"),
        "entry_fragments",
        ["entry_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_entry_fragments_page_id"),
        "entry_fragments",
        ["page_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the entry_fragments table."""
    op.drop_index(
        op.f("ix_cadmus_entry_fragments_page_id"),
        table_name="entry_fragments",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_entry_fragments_entry_id"),
        table_name="entry_fragments",
        schema="cadmus",
    )
    op.drop_table("entry_fragments", schema="cadmus")
