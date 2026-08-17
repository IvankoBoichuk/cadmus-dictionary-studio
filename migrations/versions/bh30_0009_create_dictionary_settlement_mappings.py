"""Create BH-30 dictionary settlement mapping table.

Revision ID: bh30_0009
Revises: bh30_0008
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bh30_0009"
down_revision: str | None = "bh30_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the BH-30 dictionary-scoped geographic label mapping table."""
    op.create_table(
        "dictionary_settlement_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("source_label", sa.String(length=512), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("modern_settlement_name", sa.String(length=255), nullable=True),
        sa.Column("settlement_category", sa.String(length=64), nullable=True),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("region_id", sa.Uuid(), nullable=True),
        sa.Column("community_id", sa.Uuid(), nullable=True),
        sa.Column("settlement_id", sa.Uuid(), nullable=True),
        sa.Column("community_geometry_id", sa.Uuid(), nullable=True),
        sa.Column("area_name", sa.String(length=255), nullable=True),
        sa.Column("region_name", sa.String(length=255), nullable=True),
        sa.Column("community_name", sa.String(length=255), nullable=True),
        sa.Column("external_community_id", sa.String(length=64), nullable=True),
        sa.Column("katottg", sa.String(length=32), nullable=True),
        sa.Column("koatuu", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('unresolved', 'suggested', 'confirmed')",
            name="dictionary_settlement_mapping_status",
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_id"],
            ["cadmus.dictionaries.id"],
            name=op.f("fk_dictionary_settlement_mappings_dictionary_id_dictionaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["cadmus.geography_areas.id"],
            name=op.f("fk_dictionary_settlement_mappings_area_id_geography_areas"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["region_id"],
            ["cadmus.geography_regions.id"],
            name=op.f("fk_dictionary_settlement_mappings_region_id_geography_regions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["community_id"],
            ["cadmus.geography_communities.id"],
            name=op.f(
                "fk_dictionary_settlement_mappings_community_id_geography_communities"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["cadmus.geography_settlements.id"],
            name=op.f(
                "fk_dictionary_settlement_mappings_settlement_id_geography_settlements"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["community_geometry_id"],
            ["cadmus.geography_community_geometries.id"],
            name=op.f(
                "fk_dictionary_settlement_mappings_community_geometry_id_"
                "geography_community_geometries"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_settlement_mappings_confirmed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_settlement_mappings_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["cadmus.users.id"],
            name=op.f("fk_dictionary_settlement_mappings_updated_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_settlement_mappings")),
        schema="cadmus",
    )
    op.create_index(
        op.f("ix_cadmus_dictionary_settlement_mappings_dictionary_id"),
        "dictionary_settlement_mappings",
        ["dictionary_id"],
        unique=False,
        schema="cadmus",
    )


def downgrade() -> None:
    """Remove the BH-30 dictionary-scoped geographic label mapping table."""
    op.drop_index(
        op.f("ix_cadmus_dictionary_settlement_mappings_dictionary_id"),
        table_name="dictionary_settlement_mappings",
        schema="cadmus",
    )
    op.drop_table("dictionary_settlement_mappings", schema="cadmus")
