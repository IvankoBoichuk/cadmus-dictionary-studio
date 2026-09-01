"""Account self-service: user display name, session user-agent, email-change tokens.

Revision ID: acct_0029
Revises: merge_0028
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "acct_0029"
down_revision: str | None = "merge_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add profile/session columns and the email-change token table."""
    op.add_column(
        "users",
        sa.Column("name", sa.String(length=200), nullable=True),
        schema="cadmus",
    )
    op.add_column(
        "authenticated_sessions",
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        schema="cadmus",
    )
    op.create_table(
        "email_change_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("new_email", sa.String(length=254), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_email_change_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_change_tokens")),
        sa.UniqueConstraint(
            "token_digest",
            name=op.f("uq_email_change_tokens_token_digest"),
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_email_change_tokens_user_id"),
        "email_change_tokens",
        ["user_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the email-change token table and the added columns."""
    op.drop_index(
        op.f("ix_cadmus_email_change_tokens_user_id"),
        table_name="email_change_tokens",
        schema="cadmus",
    )
    op.drop_table("email_change_tokens", schema="cadmus")
    op.drop_column("authenticated_sessions", "user_agent", schema="cadmus")
    op.drop_column("users", "name", schema="cadmus")
