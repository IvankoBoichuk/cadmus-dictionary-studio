"""Create identity users and email verification tokens.

Revision ID: bh5_0002
Revises: bh179_0001
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh5_0002"
down_revision: str | None = "bh179_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create non-lossy identity persistence for new installations."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending_verification', 'active')",
            name="account_status",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema="cadmus",
    )
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_email_verification_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_email_verification_tokens"),
        ),
        sa.UniqueConstraint(
            "token_digest",
            name=op.f("uq_email_verification_tokens_token_digest"),
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_email_verification_tokens_user_id"),
        "email_verification_tokens",
        ["user_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove only the identity data introduced by this Story.

    This is intentionally destructive for identity records and is suitable only
    after a backup or in disposable environments.
    """
    op.drop_index(
        op.f("ix_cadmus_email_verification_tokens_user_id"),
        table_name="email_verification_tokens",
        schema="cadmus",
    )
    op.drop_table("email_verification_tokens", schema="cadmus")
    op.drop_table("users", schema="cadmus")
