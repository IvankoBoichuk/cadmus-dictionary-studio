"""SQLAlchemy persistence adapters for the geography reference-data module."""

from collections.abc import Sequence
from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.geography.domain import (
    Area,
    Community,
    CommunityGeometry,
    Region,
    Settlement,
    SyncRun,
)
from cadmus.geography.ports import GeographyUnitOfWorkFactory
from cadmus.infrastructure.database import metadata

geography_registry = registry(metadata=metadata)

geography_areas = Table(
    "geography_areas",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("external_id", String(64), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column("last_synced_at", DateTime(timezone=True), nullable=False),
)

geography_regions = Table(
    "geography_regions",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("external_id", String(64), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column(
        "area_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.geography_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("last_synced_at", DateTime(timezone=True), nullable=False),
)

geography_communities = Table(
    "geography_communities",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("external_id", String(64), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column(
        "area_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.geography_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "region_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.geography_regions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("katottg", String(32), nullable=True),
    Column("koatuu", String(32), nullable=True),
    Column("admin_center_name", String(255), nullable=True),
    Column("website", String(500), nullable=True),
    Column("indicators", JSONB, nullable=True),
    Column("budgets", JSONB, nullable=True),
    Column("last_synced_at", DateTime(timezone=True), nullable=False),
)

geography_settlements = Table(
    "geography_settlements",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "community_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.geography_communities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("title", String(255), nullable=False),
    Column("category", String(64), nullable=False),
    UniqueConstraint("community_id", "title", "category"),
)

geography_community_geometries = Table(
    "geography_community_geometries",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "community_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.geography_communities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("geometry_type", String(32), nullable=False),
    Column("geometry", JSONB, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)

geography_sync_runs = Table(
    "geography_sync_runs",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("entity_type", String(16), nullable=False),
    Column("source", String(64), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("status", String(16), nullable=False),
    Column("records_synced", Integer, nullable=False),
    Column("records_failed", Integer, nullable=False),
    Column("error_message", Text, nullable=True),
)

geography_registry.map_imperatively(Area, geography_areas)
geography_registry.map_imperatively(Region, geography_regions)
geography_registry.map_imperatively(Community, geography_communities)
geography_registry.map_imperatively(Settlement, geography_settlements)
geography_registry.map_imperatively(CommunityGeometry, geography_community_geometries)
geography_registry.map_imperatively(SyncRun, geography_sync_runs)


class SqlAlchemyGeographyRepository:
    """Geography repository backed by one caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_area(self, area: Area) -> None:
        existing = self.find_area_by_external_id(area.external_id)
        if existing is None:
            self._session.add(area)
            return
        existing.name = area.name
        existing.last_synced_at = area.last_synced_at
        self._session.add(existing)

    def upsert_region(self, region: Region) -> None:
        existing = self.find_region_by_external_id(region.external_id)
        if existing is None:
            self._session.add(region)
            return
        existing.name = region.name
        existing.area_id = region.area_id
        existing.last_synced_at = region.last_synced_at
        self._session.add(existing)

    def upsert_community(
        self, community: Community, settlements: Sequence[Settlement]
    ) -> None:
        existing = self.find_community_by_external_id(community.external_id)
        if existing is None:
            self._session.add(community)
            community_id = community.id
        else:
            existing.name = community.name
            existing.area_id = community.area_id
            existing.region_id = community.region_id
            existing.katottg = community.katottg
            existing.koatuu = community.koatuu
            existing.admin_center_name = community.admin_center_name
            existing.website = community.website
            existing.indicators = community.indicators
            existing.budgets = community.budgets
            existing.last_synced_at = community.last_synced_at
            self._session.add(existing)
            community_id = existing.id

        self._replace_settlements(community_id, settlements)

    def _replace_settlements(
        self, community_id: UUID, settlements: Sequence[Settlement]
    ) -> None:
        """Diff-based upsert: preserves the local id of any settlement whose
        (title, category) already exists for this community, so a
        ``dictionary_settlement_mappings.settlement_id`` FK survives a
        routine resync. Only genuinely new or genuinely removed villages
        change the row set.
        """
        existing_rows = self._session.execute(
            select(
                geography_settlements.c.id,
                geography_settlements.c.title,
                geography_settlements.c.category,
            ).where(geography_settlements.c.community_id == community_id)
        ).all()
        existing_keys = {(row.title, row.category): row.id for row in existing_rows}

        incoming_keys: set[tuple[str, str]] = set()
        for settlement in settlements:
            key = (settlement.title, settlement.category)
            incoming_keys.add(key)
            if key in existing_keys:
                continue
            self._session.add(settlement)

        stale_ids = [
            row_id for key, row_id in existing_keys.items() if key not in incoming_keys
        ]
        if stale_ids:
            self._session.execute(
                delete(geography_settlements).where(
                    geography_settlements.c.id.in_(stale_ids)
                )
            )

    def upsert_geometry(self, geometry: CommunityGeometry) -> None:
        existing = self.get_community_geometry(geometry.community_id)
        if existing is None:
            self._session.add(geometry)
            return
        existing.geometry_type = geometry.geometry_type
        existing.geometry = geometry.geometry
        existing.fetched_at = geometry.fetched_at
        self._session.add(existing)

    def find_area_by_external_id(self, external_id: str) -> Area | None:
        return self._session.scalar(
            select(Area).where(geography_areas.c.external_id == external_id)
        )

    def find_region_by_external_id(self, external_id: str) -> Region | None:
        return self._session.scalar(
            select(Region).where(geography_regions.c.external_id == external_id)
        )

    def find_community_by_external_id(self, external_id: str) -> Community | None:
        return self._session.scalar(
            select(Community).where(geography_communities.c.external_id == external_id)
        )

    def search_settlements(
        self,
        *,
        query: str | None,
        area_id: UUID | None,
        region_id: UUID | None,
        community_id: UUID | None,
        category: str | None,
        limit: int = 25,
    ) -> list[tuple[Settlement, Community]]:
        statement = select(Settlement, Community).join(
            Community,
            geography_settlements.c.community_id == geography_communities.c.id,
        )
        if query:
            statement = statement.where(
                geography_settlements.c.title.ilike(f"%{query}%")
            )
        if community_id is not None:
            statement = statement.where(
                geography_settlements.c.community_id == community_id
            )
        if region_id is not None:
            statement = statement.where(geography_communities.c.region_id == region_id)
        if area_id is not None:
            statement = statement.where(geography_communities.c.area_id == area_id)
        if category:
            statement = statement.where(geography_settlements.c.category == category)
        statement = statement.order_by(geography_settlements.c.title).limit(limit)
        return [(row[0], row[1]) for row in self._session.execute(statement).all()]

    def get_area(self, area_id: UUID) -> Area | None:
        return self._session.get(Area, area_id)

    def get_region(self, region_id: UUID) -> Region | None:
        return self._session.get(Region, region_id)

    def get_settlement(self, settlement_id: UUID) -> Settlement | None:
        return self._session.get(Settlement, settlement_id)

    def list_areas(self) -> list[Area]:
        return list(
            self._session.scalars(select(Area).order_by(geography_areas.c.name))
        )

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        statement = select(Region).order_by(geography_regions.c.name)
        if area_id is not None:
            statement = statement.where(geography_regions.c.area_id == area_id)
        return list(self._session.scalars(statement))

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
        statement = select(Community).order_by(geography_communities.c.name)
        if area_id is not None:
            statement = statement.where(geography_communities.c.area_id == area_id)
        if region_id is not None:
            statement = statement.where(geography_communities.c.region_id == region_id)
        return list(self._session.scalars(statement))

    def get_community(self, community_id: UUID) -> Community | None:
        return self._session.get(Community, community_id)

    def get_community_geometry(self, community_id: UUID) -> CommunityGeometry | None:
        return self._session.scalar(
            select(CommunityGeometry).where(
                geography_community_geometries.c.community_id == community_id
            )
        )

    def add_sync_run(self, run: SyncRun) -> None:
        self._session.add(run)


class SqlAlchemyGeographyUnitOfWork:
    """Session-backed geography transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.geography: SqlAlchemyGeographyRepository

    def __enter__(self) -> "SqlAlchemyGeographyUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.geography = SqlAlchemyGeographyRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("geography unit of work has not been entered")
        self._session.commit()


def create_geography_unit_of_work_factory(
    engine: Engine,
) -> GeographyUnitOfWorkFactory:
    """Build a factory producing one fresh unit of work per call."""
    return lambda: SqlAlchemyGeographyUnitOfWork(engine)
