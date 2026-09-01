"""Add article_schemas.presentation_formula for BH-148 entry rendering.

Revision ID: render_0032
Revises: review_0031
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "render_0032"
down_revision: str | None = "review_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable presentation_formula (Jinja2 template) column."""
    op.add_column(
        "article_schemas",
        sa.Column("presentation_formula", sa.Text(), nullable=True),
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the presentation_formula column."""
    op.drop_column("article_schemas", "presentation_formula", schema="cadmus")
