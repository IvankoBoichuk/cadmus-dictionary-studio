"""Create article_schemas for BH-148 AI-generated article structure.

Revision ID: bh148_0022
Revises: bh148_0021
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bh148_0022"
down_revision: str | None = "bh148_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the article_schemas version-history table."""
    op.create_table(
        "article_schemas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "raw_provider_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("provider_name", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed')",
            name="article_schema_status",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_article_schemas_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_article_schemas_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_article_schemas_activated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article_schemas")),
        sa.UniqueConstraint(
            "dictionary_id",
            "version",
            name="uq_article_schemas_dictionary_version",
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_article_schemas_dictionary_id"),
        "article_schemas",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the article_schemas table."""
    op.drop_index(
        op.f("ix_cadmus_article_schemas_dictionary_id"),
        table_name="article_schemas",
        schema="cadmus",
    )
    op.drop_table("article_schemas", schema="cadmus")
