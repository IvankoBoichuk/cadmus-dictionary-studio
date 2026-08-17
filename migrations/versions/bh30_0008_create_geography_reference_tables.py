"""Create BH-30 geography reference-data tables.

Revision ID: bh30_0008
Revises: bh29_0007
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bh30_0008"
down_revision: str | None = "bh29_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add BH-30 decentralization.ua reference-data cache tables."""
    op.create_table(
        "geography_areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geography_areas")),
        sa.UniqueConstraint("external_id", name=op.f("uq_geography_areas_external_id")),
        schema="cadmus",
    )

    op.create_table(
        "geography_regions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["cadmus.geography_areas.id"],
            name=op.f("fk_geography_regions_area_id_geography_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geography_regions")),
        sa.UniqueConstraint(
            "external_id", name=op.f("uq_geography_regions_external_id")
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_geography_regions_area_id"),
        "geography_regions",
        ["area_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "geography_communities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("katottg", sa.String(length=32), nullable=True),
        sa.Column("koatuu", sa.String(length=32), nullable=True),
        sa.Column("admin_center_name", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("indicators", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("budgets", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["cadmus.geography_areas.id"],
            name=op.f("fk_geography_communities_area_id_geography_areas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["region_id"],
            ["cadmus.geography_regions.id"],
            name=op.f("fk_geography_communities_region_id_geography_regions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geography_communities")),
        sa.UniqueConstraint(
            "external_id", name=op.f("uq_geography_communities_external_id")
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_geography_communities_area_id"),
        "geography_communities",
        ["area_id"],
        unique=False,
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_geography_communities_region_id"),
        "geography_communities",
        ["region_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "geography_settlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"],
            ["cadmus.geography_communities.id"],
            name=op.f("fk_geography_settlements_community_id_geography_communities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geography_settlements")),
        sa.UniqueConstraint(
            "community_id",
            "title",
            "category",
            name=op.f("uq_geography_settlements_community_id_title_category"),
        ),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_geography_settlements_community_id"),
        "geography_settlements",
        ["community_id"],
        unique=False,
        schema="cadmus",
    )

    op.create_table(
        "geography_community_geometries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("geometry_type", sa.String(length=32), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"],
            ["cadmus.geography_communities.id"],
            name=op.f(
                "fk_geography_community_geometries_community_id_geography_communities"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geography_community_geometries")),
        sa.UniqueConstraint(
            "community_id",
            name=op.f("uq_geography_community_geometries_community_id"),
        ),
        schema="cadmus",
    )

    op.create_table(
        "geography_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("records_synced", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "entity_type IN ('area', 'region', 'community', 'geometry')",
            name="geography_sync_run_entity_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'partial', 'failed')",
            name="geography_sync_run_status",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geography_sync_runs")),
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove BH-30 geography reference-data tables."""
    op.drop_table("geography_sync_runs", schema="cadmus")

    op.drop_table("geography_community_geometries", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_geography_settlements_community_id"),
        table_name="geography_settlements",
        schema="cadmus",
    )
    op.drop_table("geography_settlements", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_geography_communities_region_id"),
        table_name="geography_communities",
        schema="cadmus",
    )
    op.drop_index(
        op.f("ix_cadmus_geography_communities_area_id"),
        table_name="geography_communities",
        schema="cadmus",
    )
    op.drop_table("geography_communities", schema="cadmus")

    op.drop_index(
        op.f("ix_cadmus_geography_regions_area_id"),
        table_name="geography_regions",
        schema="cadmus",
    )
    op.drop_table("geography_regions", schema="cadmus")

    op.drop_table("geography_areas", schema="cadmus")
