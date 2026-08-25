"""Add an optional Telegram chat id to users, for the Telegram notification channel.

Revision ID: notif_0018
Revises: box2_0017
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "notif_0018"
down_revision: str | None = "box2_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a nullable telegram_chat_id column; existing users are unaffected."""
    op.add_column(
        "users",
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the telegram_chat_id column."""
    op.drop_column("users", "telegram_chat_id", schema="cadmus")
