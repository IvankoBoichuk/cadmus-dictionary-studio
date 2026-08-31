"""Add the in_progress / processed / published dictionary statuses.

After ``scanned`` the dictionary status now tracks the lexicographic work:
``in_progress`` once decomposition begins, ``processed`` once every lexeme and
entry is ``complete`` (both applied automatically), and ``published`` by an
explicit editor action.

Revision ID: bh190_0027
Revises: bh148_0026
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "bh190_0027"
down_revision: str | None = "bh148_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "('draft', 'configured', 'scanned', 'in_progress', 'processed', 'published')"
_OLD = "('draft', 'configured', 'scanned')"


def _set_status_constraints(values: str) -> None:
    op.drop_constraint(
        "dictionary_status", "dictionaries", schema="cadmus", type_="check"
    )
    op.create_check_constraint(
        "dictionary_status",
        "dictionaries",
        f"status IN {values}",
        schema="cadmus",
    )
    for column in ("previous_status", "new_status"):
        name = f"dictionary_event_{column}"
        op.drop_constraint(name, "dictionary_events", schema="cadmus", type_="check")
        op.create_check_constraint(
            name,
            "dictionary_events",
            f"{column} IS NULL OR {column} IN {values}",
            schema="cadmus",
        )


def upgrade() -> None:
    """Allow the three new statuses on dictionaries and the audit columns."""
    _set_status_constraints(_NEW)


def downgrade() -> None:
    """Revert to draft/configured/scanned.

    Only safe if no row already uses one of the new statuses -- matches this
    codebase's posture of not attempting automatic data backfill on downgrade.
    """
    _set_status_constraints(_OLD)
