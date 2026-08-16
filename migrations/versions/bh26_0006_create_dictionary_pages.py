"""Create dictionary_pages and page-split tracking on dictionary_source_files.

Revision ID: bh26_0006
Revises: bh26_0005
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh26_0006"
down_revision: str | None = "bh26_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add per-page splitting (ADR-0006) without touching prior data."""
    op.add_column(
        "dictionary_source_files",
        sa.Column(
            "pages_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        schema="cadmus",
    )
    op.add_column(
        "dictionary_source_files",
        sa.Column("pages_error", sa.Text(), nullable=True),
        schema="cadmus",
    )
    op.create_check_constraint(
        "source_file_pages_status",
        "dictionary_source_files",
        "pages_status IN ('pending', 'completed', 'failed')",
        schema="cadmus",
    )

    op.create_table(
        "dictionary_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("printed_page_number", sa.Integer(), nullable=True),
        sa.Column("processed_asset_key", sa.String(length=500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("rotation", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("ocr_status", sa.String(length=16), nullable=False),
        sa.Column("layout_status", sa.String(length=16), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ocr_status IN ('pending', 'processing', 'completed', 'failed')",
            name="dictionary_page_ocr_status",
        ),
        sa.CheckConstraint(
            "layout_status IN ('pending', 'processing', 'completed', 'failed')",
            name="dictionary_page_layout_status",
        ),
        sa.CheckConstraint(
            "validation_status IN ('pending', 'processing', 'completed', 'failed')",
            name="dictionary_page_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["cadmus.dictionary_source_files.id"],
            name=op.f("fk_dictionary_pages_source_file_id_dictionary_source_files"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_pages")),
        sa.UniqueConstraint(
            "source_file_id",
            "page_index",
            name="uq_dictionary_pages_source_file_page",
        ),
        sa.UniqueConstraint(
            "processed_asset_key",
            name=op.f("uq_dictionary_pages_processed_asset_key"),
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_pages_source_file_id"),
        "dictionary_pages",
        ["source_file_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove per-page splitting after backup or in disposable envs."""
    op.drop_index(
        op.f("ix_cadmus_dictionary_pages_source_file_id"),
        table_name="dictionary_pages",
        schema="cadmus",
    )
    op.drop_table("dictionary_pages", schema="cadmus")

    op.drop_constraint(
        "source_file_pages_status",
        "dictionary_source_files",
        schema="cadmus",
        type_="check",
    )
    op.drop_column("dictionary_source_files", "pages_error", schema="cadmus")
    op.drop_column("dictionary_source_files", "pages_status", schema="cadmus")
