"""Create the review-queue reviewer-decision audit trail table.

Records each reviewer verdict on a dictionary entry -- approve
(``READY_TO_REVIEW -> COMPLETE``) or send back (``READY_TO_REVIEW ->
DRAFT``) -- for the cross-dictionary ``/review`` queue.

Revision ID: review_0031
Revises: merge_0030
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "review_0031"
down_revision: str | None = "merge_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the append-only reviewer-decision history table.

    ``entry_id`` is intentionally not a foreign key to ``dictionary_entries``:
    a decision must remain readable after the entry row is gone (same
    rationale as ``lexeme_events`` -- audit trail is append-oriented).
    """
    op.create_table(
        "review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "decision IN ('approved', 'sent_back')",
            name="ck_review_events_review_event_decision",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_review_events_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["cadmus.users.id"],
            name=op.f("fk_review_events_reviewer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_events")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_review_events_entry_id"),
        "review_events",
        ["entry_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_review_events_dictionary_id"),
        "review_events",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_review_events_occurred_at"),
        "review_events",
        ["occurred_at"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the reviewer-decision audit trail table."""
    op.drop_index(
        op.f("ix_cadmus_review_events_occurred_at"),
        table_name="review_events",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_review_events_dictionary_id"),
        table_name="review_events",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_review_events_entry_id"),
        table_name="review_events",
        schema="cadmus",
    )
    op.drop_table("review_events", schema="cadmus")
