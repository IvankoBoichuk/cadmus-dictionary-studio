"""Add Google identities and allow password-less accounts.

Revision ID: bh188_0012
Revises: bh28_0011
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh188_0012"
down_revision: str | None = "bh28_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the BH-188 Google identity table and relax the password requirement."""
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
        schema="cadmus",
    )
    op.create_table(
        "google_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_google_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_identities")),
        sa.UniqueConstraint("subject", name=op.f("uq_google_identities_subject")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_google_identities_user_id"),
        "google_identities",
        ["user_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the BH-188 Google identity table and restore the password requirement.

    Intentionally destructive for Google identity records and is suitable only
    after a backup or in disposable environments. Any password-less account
    created via Google sign-in will violate the restored NOT NULL constraint
    and must be cleaned up (or given a password) before downgrading.
    """
    op.drop_index(
        op.f("ix_cadmus_google_identities_user_id"),
        table_name="google_identities",
        schema="cadmus",
    )
    op.drop_table("google_identities", schema="cadmus")
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
        schema="cadmus",
    )
