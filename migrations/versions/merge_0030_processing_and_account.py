"""Merge the two 0029 heads into one lineage.

`proc_0029` (processing_tasks registry for async job monitoring) and
`acct_0029` (account self-service) both branched from `merge_0028`,
leaving Alembic with two heads. They touch disjoint schema (a new
monitoring table vs. account-management columns/tables), so this is a
pure merge point with no DDL of its own.

Revision ID: merge_0030
Revises: proc_0029, acct_0029
Create Date: 2026-09-01
"""

from collections.abc import Sequence

revision: str = "merge_0030"
down_revision: tuple[str, ...] = ("proc_0029", "acct_0029")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: this revision only reunites the two migration heads."""


def downgrade() -> None:
    """No-op: downgrading past this splits the lineage back into two heads."""
