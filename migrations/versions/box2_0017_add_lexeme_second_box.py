"""Add an optional second bounding box to lexemes (entries split across a column).

Revision ID: box2_0017
Revises: ocr_0016
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "box2_0017"
down_revision: str | None = "ocr_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_OR_NONE_CHECK = (
    "(x2 IS NULL) = (y2 IS NULL) AND (y2 IS NULL) = (width2 IS NULL) "
    "AND (width2 IS NULL) = (height2 IS NULL)"
)


def upgrade() -> None:
    """Add nullable x2/y2/width2/height2 for a second, same-page box."""
    op.add_column(
        "lexemes", sa.Column("x2", sa.Float(), nullable=True), schema="cadmus"
    )
    op.add_column(
        "lexemes", sa.Column("y2", sa.Float(), nullable=True), schema="cadmus"
    )
    op.add_column(
        "lexemes", sa.Column("width2", sa.Float(), nullable=True), schema="cadmus"
    )
    op.add_column(
        "lexemes", sa.Column("height2", sa.Float(), nullable=True), schema="cadmus"
    )
    op.create_check_constraint(
        "lexeme_second_box_all_or_none",
        "lexemes",
        _ALL_OR_NONE_CHECK,
        schema="cadmus",
    )
    op.create_check_constraint(
        "lexeme_second_box_positive_size",
        "lexemes",
        "width2 IS NULL OR (width2 > 0 AND height2 > 0)",
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the second-box columns and their constraints."""
    op.drop_constraint(
        "lexeme_second_box_positive_size", "lexemes", schema="cadmus", type_="check"
    )
    op.drop_constraint(
        "lexeme_second_box_all_or_none", "lexemes", schema="cadmus", type_="check"
    )
    op.drop_column("lexemes", "height2", schema="cadmus")
    op.drop_column("lexemes", "width2", schema="cadmus")
    op.drop_column("lexemes", "y2", schema="cadmus")
    op.drop_column("lexemes", "x2", schema="cadmus")
