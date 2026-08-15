"""Create server-side authenticated sessions.

Revision ID: bh3_0003
Revises: bh5_0002
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh3_0003"
down_revision: str | None = "bh5_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add non-plaintext session persistence without changing user records."""
    op.create_table(
        "authenticated_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_authenticated_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_authenticated_sessions")),
        sa.UniqueConstraint(
            "token_digest",
            name=op.f("uq_authenticated_sessions_token_digest"),
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_authenticated_sessions_user_id"),
        "authenticated_sessions",
        ["user_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_authenticated_sessions_expires_at"),
        "authenticated_sessions",
        ["expires_at"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove session records after backup or in disposable environments."""
    op.drop_index(
        op.f("ix_cadmus_authenticated_sessions_expires_at"),
        table_name="authenticated_sessions",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_authenticated_sessions_user_id"),
        table_name="authenticated_sessions",
        schema="cadmus",
    )
    op.drop_table("authenticated_sessions", schema="cadmus")
