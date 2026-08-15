"""Create password reset tokens.

Revision ID: bh10_0004
Revises: bh3_0003
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh10_0004"
down_revision: str | None = "bh3_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create non-lossy password-reset-token persistence for new installations."""
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_password_reset_tokens"),
        ),
        sa.UniqueConstraint(
            "token_digest",
            name=op.f("uq_password_reset_tokens_token_digest"),
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove only the password-reset data introduced by this Story.

    This is intentionally destructive for reset-token records and is suitable
    only after a backup or in disposable environments.
    """
    op.drop_index(
        op.f("ix_cadmus_password_reset_tokens_user_id"),
        table_name="password_reset_tokens",
        schema="cadmus",
    )
    op.drop_table("password_reset_tokens", schema="cadmus")
