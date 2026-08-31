"""Create versioned reference lexicon data and entry mappings.

Revision ID: vesum_0027
Revises: bh148_0026
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "vesum_0027"
down_revision: str | None = "bh148_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_lexicons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("license_id", sa.String(length=64), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        schema="cadmus",
    )

    op.create_table(
        "reference_lemmas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lexicon_id", sa.Uuid(), nullable=False),
        sa.Column("external_key", sa.String(length=700), nullable=False),
        sa.Column("lemma", sa.String(length=500), nullable=False),
        sa.Column("normalized_lemma", sa.String(length=500), nullable=False),
        sa.Column("part_of_speech", sa.String(length=32), nullable=False),
        sa.Column(
            "key_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("is_standard", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lexicon_id"],
            ["cadmus.reference_lexicons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lexicon_id",
            "external_key",
            name="uq_reference_lemmas_lexicon_external_key",
        ),
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_reference_lemmas_lexicon_id",
        "reference_lemmas",
        ["lexicon_id"],
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_reference_lemmas_normalized_lemma",
        "reference_lemmas",
        ["normalized_lemma"],
        schema="cadmus",
    )

    op.create_table(
        "reference_word_forms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lemma_id", sa.Uuid(), nullable=False),
        sa.Column("form", sa.String(length=500), nullable=False),
        sa.Column("normalized_form", sa.String(length=500), nullable=False),
        sa.Column("morphology", sa.Text(), nullable=False),
        sa.Column("is_standard", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lemma_id"],
            ["cadmus.reference_lemmas.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_reference_word_forms_lemma_id",
        "reference_word_forms",
        ["lemma_id"],
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_reference_word_forms_normalized_form",
        "reference_word_forms",
        ["normalized_form"],
        schema="cadmus",
    )

    op.create_table(
        "entry_reference_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("reference_lemma_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "relation_type IN "
            "('standard_equivalent', 'synonym', 'approximate_equivalent', "
            "'hypernym', 'related')",
            name="ck_entry_reference_links_entry_reference_link_relation_type",
        ),
        sa.CheckConstraint(
            "origin IN ('manual')",
            name="ck_entry_reference_links_entry_reference_link_origin",
        ),
        sa.CheckConstraint(
            "validation_status IN ('confirmed')",
            name="ck_entry_reference_links_entry_reference_link_validation_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_entry_reference_links_entry_reference_link_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["cadmus.users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["cadmus.dictionary_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reference_lemma_id"],
            ["cadmus.reference_lemmas.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entry_id",
            "reference_lemma_id",
            "relation_type",
            name="uq_entry_reference_links_entry_lemma_relation",
        ),
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_entry_reference_links_entry_id",
        "entry_reference_links",
        ["entry_id"],
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_entry_reference_links_reference_lemma_id",
        "entry_reference_links",
        ["reference_lemma_id"],
        schema="cadmus",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cadmus_entry_reference_links_reference_lemma_id",
        table_name="entry_reference_links",
        schema="cadmus",
    )
    op.drop_index(
        "ix_cadmus_entry_reference_links_entry_id",
        table_name="entry_reference_links",
        schema="cadmus",
    )
    op.drop_table("entry_reference_links", schema="cadmus")
    op.drop_index(
        "ix_cadmus_reference_word_forms_normalized_form",
        table_name="reference_word_forms",
        schema="cadmus",
    )
    op.drop_index(
        "ix_cadmus_reference_word_forms_lemma_id",
        table_name="reference_word_forms",
        schema="cadmus",
    )
    op.drop_table("reference_word_forms", schema="cadmus")
    op.drop_index(
        "ix_cadmus_reference_lemmas_normalized_lemma",
        table_name="reference_lemmas",
        schema="cadmus",
    )
    op.drop_index(
        "ix_cadmus_reference_lemmas_lexicon_id",
        table_name="reference_lemmas",
        schema="cadmus",
    )
    op.drop_table("reference_lemmas", schema="cadmus")
    op.drop_table("reference_lexicons", schema="cadmus")
