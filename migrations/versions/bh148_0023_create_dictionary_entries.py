"""Create dictionary_entries for BH-148 (a lexeme promoted to an article).

Revision ID: bh148_0023
Revises: bh148_0022
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh148_0023"
down_revision: str | None = "bh148_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the dictionary_entries table (ADR-0006 DictionaryEntry)."""
    op.create_table(
        "dictionary_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("lexeme_id", sa.Uuid(), nullable=False),
        sa.Column("headword", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("schema_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'ready_to_review', 'complete')",
            name="dictionary_entry_status",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_entries_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lexeme_id"],
            ["cadmus.lexemes.id"],
            name=op.f("fk_dictionary_entries_lexeme_id_lexemes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schema_id"],
            ["cadmus.article_schemas.id"],
            name=op.f("fk_dictionary_entries_schema_id_article_schemas"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_entries_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_entries_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_entries")),
        sa.UniqueConstraint("lexeme_id", name=op.f("uq_dictionary_entries_lexeme_id")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_entries_dictionary_id"),
        "dictionary_entries",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the dictionary_entries table."""
    op.drop_index(
        op.f("ix_cadmus_dictionary_entries_dictionary_id"),
        table_name="dictionary_entries",
        schema="cadmus",
    )
    op.drop_table("dictionary_entries", schema="cadmus")
