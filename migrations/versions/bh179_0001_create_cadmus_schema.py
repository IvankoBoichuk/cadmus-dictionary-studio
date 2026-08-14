"""Create the Cadmus application schema.

Revision ID: bh179_0001
Revises:
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.schema import CreateSchema, DropSchema

revision: str = "bh179_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the namespace for future Cadmus persistence models."""
    op.execute(CreateSchema("cadmus"))


def downgrade() -> None:
    """Remove the empty Cadmus namespace."""
    op.execute(DropSchema("cadmus"))
