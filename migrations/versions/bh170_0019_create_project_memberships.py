"""Create project_memberships for BH-170 role-based project access.

Revision ID: bh170_0019
Revises: notif_0018
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh170_0019"
down_revision: str | None = "notif_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the project_memberships table (non-owner collaborators only)."""
    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "role IN ('editor', 'reviewer', 'viewer')", name="project_membership_role"
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_project_memberships_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_project_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_project_memberships_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_project_memberships_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_memberships")),
        sa.UniqueConstraint(
            "dictionary_id",
            "user_id",
            name="uq_project_memberships_dictionary_id_user_id",
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_project_memberships_dictionary_id"),
        "project_memberships",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_project_memberships_user_id"),
        "project_memberships",
        ["user_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the project_memberships table."""
    op.drop_index(
        op.f("ix_cadmus_project_memberships_user_id"),
        table_name="project_memberships",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_project_memberships_dictionary_id"),
        table_name="project_memberships",
        schema="cadmus",
    )
    op.drop_table("project_memberships", schema="cadmus")
