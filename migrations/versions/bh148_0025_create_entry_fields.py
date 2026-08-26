"""Create entry_fields for BH-148: structured, provenance-tracked article fields.

Revision ID: bh148_0025
Revises: bh148_0024
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh148_0025"
down_revision: str | None = "bh148_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the entry_fields table.

    ``parent_field_id`` self-references ``entry_fields`` to support
    repeating and nested elements (e.g. several ``meaning`` fields, each
    with its own ``example``/``synonym`` children).
    """
    op.create_table(
        "entry_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("fragment_id", sa.Uuid(), nullable=False),
        sa.Column("parent_field_id", sa.Uuid(), nullable=True),
        sa.Column("field_path", sa.String(length=500), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "role IN ('headword', 'part_of_speech', 'meaning', 'example', "
            "'synonym', 'abbreviation', 'geographic_label', 'other')",
            name="entry_field_role",
        ),
        sa.CheckConstraint(
            "origin IN ('model', 'rule', 'manual')", name="entry_field_origin"
        ),
        sa.CheckConstraint(
            "source_end >= source_start", name="entry_field_positive_span"
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["cadmus.dictionary_entries.id"],
            name=op.f("fk_entry_fields_entry_id_dictionary_entries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fragment_id"],
            ["cadmus.entry_fragments.id"],
            name=op.f("fk_entry_fields_fragment_id_entry_fragments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_field_id"],
            ["cadmus.entry_fields.id"],
            name=op.f("fk_entry_fields_parent_field_id_entry_fields"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_entry_fields_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_entry_fields_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_fields")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_entry_fields_entry_id"),
        "entry_fields",
        ["entry_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_entry_fields_fragment_id"),
        "entry_fields",
        ["fragment_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_entry_fields_parent_field_id"),
        "entry_fields",
        ["parent_field_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the entry_fields table."""
    op.drop_index(
        op.f("ix_cadmus_entry_fields_parent_field_id"),
        table_name="entry_fields",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_entry_fields_fragment_id"),
        table_name="entry_fields",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_entry_fields_entry_id"),
        table_name="entry_fields",
        schema="cadmus",
    )
    op.drop_table("entry_fields", schema="cadmus")
