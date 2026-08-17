"""Add BH-31 status-transition audit columns to dictionary_events.

Revision ID: bh31_0010
Revises: bh30_0009
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh31_0010"
down_revision: str | None = "bh30_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record previous/new status and an optional reason on status events."""
    op.add_column(
        "dictionary_events",
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        schema="cadmus",
    )
    op.add_column(
        "dictionary_events",
        sa.Column("new_status", sa.String(length=32), nullable=True),
        schema="cadmus",
    )
    op.add_column(
        "dictionary_events",
        sa.Column("reason", sa.String(length=255), nullable=True),
        schema="cadmus",
    )
    op.drop_constraint(
        "dictionary_event_type",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.create_check_constraint(
        "dictionary_event_type",
        "dictionary_events",
        "event_type IN "
        "('created', 'source_uploaded', 'metadata_updated', 'status_changed')",
        schema="cadmus",
    )
    op.create_check_constraint(
        "dictionary_event_previous_status",
        "dictionary_events",
        "previous_status IS NULL OR previous_status IN ('draft', 'configured')",
        schema="cadmus",
    )
    op.create_check_constraint(
        "dictionary_event_new_status",
        "dictionary_events",
        "new_status IS NULL OR new_status IN ('draft', 'configured')",
        schema="cadmus",
    )


def downgrade() -> None:
    """Drop the BH-31 status-transition audit columns and constraints."""
    op.drop_constraint(
        "dictionary_event_new_status",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.drop_constraint(
        "dictionary_event_previous_status",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.drop_constraint(
        "dictionary_event_type",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.create_check_constraint(
        "dictionary_event_type",
        "dictionary_events",
        "event_type IN ('created', 'source_uploaded', 'metadata_updated')",
        schema="cadmus",
    )
    op.drop_column("dictionary_events", "reason", schema="cadmus")
    op.drop_column("dictionary_events", "new_status", schema="cadmus")
    op.drop_column("dictionary_events", "previous_status", schema="cadmus")
