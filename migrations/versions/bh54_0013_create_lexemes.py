"""Create the BH-54 manual lexeme selection table.

Revision ID: bh54_0013
Revises: bh188_0012
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh54_0013"
down_revision: str | None = "bh188_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the BH-54 manually selected lexeme table."""
    op.create_table(
        "lexemes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("source_text", sa.String(length=500), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint("origin IN ('manual')", name="lexeme_origin"),
        sa.CheckConstraint("width > 0 AND height > 0", name="lexeme_positive_size"),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_lexemes_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["cadmus.dictionary_pages.id"],
            name=op.f("fk_lexemes_page_id_dictionary_pages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_lexemes_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_lexemes_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lexemes")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_lexemes_dictionary_id"),
        "lexemes",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_lexemes_page_id"),
        "lexemes",
        ["page_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the BH-54 manually selected lexeme table."""
    op.drop_index(
        op.f("ix_cadmus_lexemes_page_id"), table_name="lexemes", schema="cadmus"
    )
    op.drop_index(
        op.f("ix_cadmus_lexemes_dictionary_id"), table_name="lexemes", schema="cadmus"
    )
    op.drop_table("lexemes", schema="cadmus")
