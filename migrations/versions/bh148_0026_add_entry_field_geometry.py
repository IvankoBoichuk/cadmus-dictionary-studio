"""Add entry_field geometry for BH-148 ALTO segmentation (experimental variant 1).

An extracted field's source span can now be a real page-pixel bounding box
(the union of the OCR word segments it was built from) instead of only a
character offset into its fragment's recognized_text -- ``source_start``/
``source_end`` become optional so a field can carry either, both, or
neither kind of span.

Revision ID: bh148_0026
Revises: bh148_0025
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh148_0026"
down_revision: str | None = "bh148_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable x/y/width/height columns and relax source_start/source_end."""
    op.add_column(
        "entry_fields", sa.Column("x", sa.Float(), nullable=True), schema="cadmus"
    )
    op.add_column(
        "entry_fields", sa.Column("y", sa.Float(), nullable=True), schema="cadmus"
    )
    op.add_column(
        "entry_fields", sa.Column("width", sa.Float(), nullable=True), schema="cadmus"
    )
    op.add_column(
        "entry_fields", sa.Column("height", sa.Float(), nullable=True), schema="cadmus"
    )
    op.alter_column("entry_fields", "source_start", nullable=True, schema="cadmus")
    op.alter_column("entry_fields", "source_end", nullable=True, schema="cadmus")


def downgrade() -> None:
    """Remove the geometry columns and restore source_start/source_end as required."""
    op.alter_column("entry_fields", "source_end", nullable=False, schema="cadmus")
    op.alter_column("entry_fields", "source_start", nullable=False, schema="cadmus")
    op.drop_column("entry_fields", "height", schema="cadmus")
    op.drop_column("entry_fields", "width", schema="cadmus")
    op.drop_column("entry_fields", "y", schema="cadmus")
    op.drop_column("entry_fields", "x", schema="cadmus")
