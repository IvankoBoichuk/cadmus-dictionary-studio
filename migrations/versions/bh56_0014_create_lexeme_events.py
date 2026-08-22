"""Create the BH-56 lexeme edit/delete audit trail table.

Revision ID: bh56_0014
Revises: bh54_0013
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bh56_0014"
down_revision: str | None = "bh54_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the BH-56 append-only lexeme edit/delete history table.

    ``lexeme_id`` is intentionally not a foreign key to ``lexemes``: a
    deletion event must remain readable after the lexeme row itself is
    gone (ADR-0004 -- audit trail is append-oriented).
    """
    op.create_table(
        "lexeme_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lexeme_id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.CheckConstraint(
            "event_type IN ('updated', 'deleted')", name="lexeme_event_type"
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_lexeme_events_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_lexeme_events_actor_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lexeme_events")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_lexeme_events_lexeme_id"),
        "lexeme_events",
        ["lexeme_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_lexeme_events_dictionary_id"),
        "lexeme_events",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_lexeme_events_occurred_at"),
        "lexeme_events",
        ["occurred_at"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the BH-56 lexeme edit/delete audit trail table."""
    op.drop_index(
        op.f("ix_cadmus_lexeme_events_occurred_at"),
        table_name="lexeme_events",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_lexeme_events_dictionary_id"),
        table_name="lexeme_events",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_lexeme_events_lexeme_id"),
        table_name="lexeme_events",
        schema="cadmus",
    )
    op.drop_table("lexeme_events", schema="cadmus")
