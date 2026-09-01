"""Create the processing_tasks registry for async job monitoring.

Revision ID: proc_0029
Revises: merge_0028
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "proc_0029"
down_revision: str | None = "merge_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = (
    "dictionary_scan",
    "entry_extraction",
    "article_schema_generation",
    "ocr_suggestions",
)
_STATUSES = ("queued", "running", "succeeded", "failed")


def upgrade() -> None:
    op.create_table(
        "processing_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("celery_task_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("target_label", sa.String(length=255), nullable=True),
        sa.Column(
            "rerun_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enqueued_by", sa.Uuid(), nullable=False),
        sa.Column("retry_of_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('" + "', '".join(_KINDS) + "')",
            name="ck_processing_tasks_kind",
        ),
        sa.CheckConstraint(
            "status IN ('" + "', '".join(_STATUSES) + "')",
            name="ck_processing_tasks_status",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"], ["cadmus.dictionaries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["enqueued_by"], ["cadmus.users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_id"], ["cadmus.processing_tasks.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "celery_task_id", name="uq_processing_tasks_celery_task_id"
        ),
        schema="cadmus",
    )
    op.create_index(
        "ix_cadmus_processing_tasks_dictionary_id_created_at",
        "processing_tasks",
        ["dictionary_id", sa.text("created_at DESC")],
        schema="cadmus",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cadmus_processing_tasks_dictionary_id_created_at",
        table_name="processing_tasks",
        schema="cadmus",
    )
    op.drop_table("processing_tasks", schema="cadmus")
