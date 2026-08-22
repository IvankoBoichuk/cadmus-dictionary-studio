"""Allow 'ocr' as a lexeme origin (OCR-suggested lexemes).

Revision ID: ocr_0016
Revises: bh58_0015
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "ocr_0016"
down_revision: str | None = "bh58_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen lexemes.origin to accept OCR-suggested lexemes alongside manual ones."""
    op.drop_constraint("lexeme_origin", "lexemes", schema="cadmus", type_="check")
    op.create_check_constraint(
        "lexeme_origin",
        "lexemes",
        "origin IN ('manual', 'ocr')",
        schema="cadmus",
    )


def downgrade() -> None:
    """Revert to manual-only lexemes.

    Only safe if no row already uses 'ocr' -- matches this codebase's
    existing posture of not attempting automatic data backfill on downgrade.
    """
    op.drop_constraint("lexeme_origin", "lexemes", schema="cadmus", type_="check")
    op.create_check_constraint(
        "lexeme_origin",
        "lexemes",
        "origin IN ('manual')",
        schema="cadmus",
    )
