"""Add article_description to dictionaries (BH-148).

Revision ID: bh148_0021
Revises: bh113_0020
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh148_0021"
down_revision: str | None = "bh113_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the free-text article structure description setting."""
    op.add_column(
        "dictionaries",
        sa.Column("article_description", sa.Text(), nullable=True),
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the article structure description setting."""
    op.drop_column("dictionaries", "article_description", schema="cadmus")
