"""Add the BH-58 'scanned' dictionary status.

Revision ID: bh58_0015
Revises: bh56_0014
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "bh58_0015"
down_revision: str | None = "bh56_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow 'scanned' on dictionaries.status and dictionary_events' audit columns."""
    op.drop_constraint(
        "dictionary_status", "dictionaries", schema="cadmus", type_="check"
    )
    op.create_check_constraint(
        "dictionary_status",
        "dictionaries",
        "status IN ('draft', 'configured', 'scanned')",
        schema="cadmus",
    )
    op.drop_constraint(
        "dictionary_event_previous_status",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.create_check_constraint(
        "dictionary_event_previous_status",
        "dictionary_events",
        "previous_status IS NULL OR previous_status IN "
        "('draft', 'configured', 'scanned')",
        schema="cadmus",
    )
    op.drop_constraint(
        "dictionary_event_new_status",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.create_check_constraint(
        "dictionary_event_new_status",
        "dictionary_events",
        "new_status IS NULL OR new_status IN ('draft', 'configured', 'scanned')",
        schema="cadmus",
    )


def downgrade() -> None:
    """Revert to draft/configured only.

    Only safe if no row already uses 'scanned' -- matches this codebase's
    existing posture of not attempting automatic data backfill on downgrade.
    """
    op.drop_constraint(
        "dictionary_event_new_status",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.create_check_constraint(
        "dictionary_event_new_status",
        "dictionary_events",
        "new_status IS NULL OR new_status IN ('draft', 'configured')",
        schema="cadmus",
    )
    op.drop_constraint(
        "dictionary_event_previous_status",
        "dictionary_events",
        schema="cadmus",
        type_="check",
    )
    op.create_check_constraint(
        "dictionary_event_previous_status",
        "dictionary_events",
        "previous_status IS NULL OR previous_status IN ('draft', 'configured')",
        schema="cadmus",
    )
    op.drop_constraint(
        "dictionary_status", "dictionaries", schema="cadmus", type_="check"
    )
    op.create_check_constraint(
        "dictionary_status",
        "dictionaries",
        "status IN ('draft', 'configured')",
        schema="cadmus",
    )
