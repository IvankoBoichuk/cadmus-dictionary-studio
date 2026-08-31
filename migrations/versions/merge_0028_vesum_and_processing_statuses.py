"""Merge the two 0027 heads into one lineage.

`bh190_0027` (dictionary processing statuses, PR #42) and `vesum_0027`
(VESUM reference lexicon, PR #43) both branched from `bh148_0026`, leaving
Alembic with two heads. They touch disjoint schema (a CHECK-constraint
widening vs. new reference-lexicon tables), so this is a pure merge point
with no DDL of its own.

Revision ID: merge_0028
Revises: bh190_0027, vesum_0027
Create Date: 2026-09-01
"""

from collections.abc import Sequence

revision: str = "merge_0028"
down_revision: tuple[str, ...] = ("bh190_0027", "vesum_0027")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: this revision only reunites the two migration heads."""


def downgrade() -> None:
    """No-op: downgrading past this splits the lineage back into two heads."""
