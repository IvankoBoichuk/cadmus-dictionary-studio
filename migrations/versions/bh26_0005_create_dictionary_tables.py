"""Create dictionary draft, source file, metadata, and audit tables.

Revision ID: bh26_0005
Revises: bh10_0004
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bh26_0005"
down_revision: str | None = "bh10_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the BH-26/BH-27 dictionary draft aggregate without touching prior data."""
    op.create_table(
        "dictionaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dictionary_type", sa.String(length=255), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("edition", sa.String(length=255), nullable=True),
        sa.Column("isbn", sa.String(length=20), nullable=True),
        sa.Column("digital_source", sa.String(length=500), nullable=True),
        sa.Column("legal_status", sa.String(length=32), nullable=True),
        sa.Column("license_type", sa.String(length=255), nullable=True),
        sa.Column("permission_reference", sa.String(length=500), nullable=True),
        sa.Column("rights_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'configured')", name="dictionary_status"
        ),
        sa.CheckConstraint(
            "legal_status IS NULL OR legal_status IN "
            "('public_domain', 'licensed', 'permission_granted', 'restricted', "
            "'unknown')",
            name="dictionary_legal_status",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionaries_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionaries_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionaries")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionaries_owner_id"),
        "dictionaries",
        ["owner_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "dictionary_contributors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("role IN ('author', 'compiler')", name="contributor_role"),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_contributors_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_contributors")),
        sa.UniqueConstraint(
            "dictionary_id",
            "position",
            name="uq_dictionary_contributors_dictionary_id_position",
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_contributors_dictionary_id"),
        "dictionary_contributors",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "dictionary_languages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("language_code", sa.String(length=2), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_languages_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_languages")),
        sa.UniqueConstraint(
            "dictionary_id",
            "language_code",
            name="uq_dictionary_languages_dictionary_id_language_code",
        ),
        sa.UniqueConstraint(
            "dictionary_id",
            "position",
            name="uq_dictionary_languages_dictionary_id_position",
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_languages_dictionary_id"),
        "dictionary_languages",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "dictionary_source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("inspection_status", sa.String(length=16), nullable=False),
        sa.Column("inspection_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "inspection_status IN ('pending', 'verified', 'failed')",
            name="source_file_inspection_status",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_source_files_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_source_files_uploaded_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_source_files")),
        sa.UniqueConstraint(
            "dictionary_id", name=op.f("uq_dictionary_source_files_dictionary_id")
        ),
        sa.UniqueConstraint(
            "storage_key", name=op.f("uq_dictionary_source_files_storage_key")
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_source_files_checksum_sha256"),
        "dictionary_source_files",
        ["checksum_sha256"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "dictionary_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'source_uploaded', 'metadata_updated')",
            name="dictionary_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_events_actor_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_events_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_events")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_events_dictionary_id"),
        "dictionary_events",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_events_occurred_at"),
        "dictionary_events",
        ["occurred_at"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the dictionary draft aggregate after backup or in disposable envs."""
    op.drop_index(
        op.f("ix_cadmus_dictionary_events_occurred_at"),
        table_name="dictionary_events",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_dictionary_events_dictionary_id"),
        table_name="dictionary_events",
        schema="cadmus",
    )
    op.drop_table("dictionary_events", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_dictionary_source_files_checksum_sha256"),
        table_name="dictionary_source_files",
        schema="cadmus",
    )
    op.drop_table("dictionary_source_files", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_dictionary_languages_dictionary_id"),
        table_name="dictionary_languages",
        schema="cadmus",
    )
    op.drop_table("dictionary_languages", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_dictionary_contributors_dictionary_id"),
        table_name="dictionary_contributors",
        schema="cadmus",
    )
    op.drop_table("dictionary_contributors", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_dictionaries_owner_id"),
        table_name="dictionaries",
        schema="cadmus",
    )
    op.drop_table("dictionaries", schema="cadmus")
