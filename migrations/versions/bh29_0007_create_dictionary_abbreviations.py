"""Create dictionary_abbreviations and dictionary_abbreviation_variants.

Revision ID: bh29_0007
Revises: bh26_0006
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh29_0007"
down_revision: str | None = "bh26_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add BH-29 dictionary-scoped abbreviation configuration tables."""
    op.create_table(
        "dictionary_abbreviations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("abbreviation", sa.String(length=64), nullable=False),
        sa.Column("full_form", sa.String(length=512), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("language_code", sa.String(length=2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("unresolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "category IN ('part_of_speech', 'grammar', 'usage', 'geography', "
            "'source', 'other')",
            name="dictionary_abbreviation_category",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_abbreviations_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_abbreviations_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_abbreviations_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_abbreviations")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_abbreviations_dictionary_id"),
        "dictionary_abbreviations",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "dictionary_abbreviation_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("abbreviation_id", sa.Uuid(), nullable=False),
        sa.Column("variant_text", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["abbreviation_id"],
            ["cadmus.dictionary_abbreviations.id"],
            name=op.f("fk_abbreviation_variants_abbreviation_id_abbreviations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_abbreviation_variants")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_abbreviation_variants_abbreviation_id"),
        "dictionary_abbreviation_variants",
        ["abbreviation_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove BH-29 abbreviation tables after backup or in disposable envs."""
    op.drop_index(
        op.f("ix_cadmus_dictionary_abbreviation_variants_abbreviation_id"),
        table_name="dictionary_abbreviation_variants",
        schema="cadmus",
    )
    op.drop_table("dictionary_abbreviation_variants", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_dictionary_abbreviations_dictionary_id"),
        table_name="dictionary_abbreviations",
        schema="cadmus",
    )
    op.drop_table("dictionary_abbreviations", schema="cadmus")
