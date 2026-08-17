"""BH-30 geography reference-data sync orchestration.

``SyncGeographyService.sync_all()`` fetches each entity type from
``decentralization.ua`` fully outside any DB transaction, then upserts it in
its own transaction. A failure syncing one entity type is caught, logged,
and recorded as a ``SyncRun`` -- it never rolls back or blocks entity types
that already succeeded (AC15), and previously-synced data stays queryable
through ``GeographyRepository`` regardless of the current run's outcome.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.geography.domain import (
    Area,
    Community,
    CommunityGeometry,
    DecentralizationParseError,
    GeographyEntityType,
    GeographySyncStatus,
    Region,
    SyncRun,
    parse_area,
    parse_community,
    parse_geo_json,
    parse_region,
)
from cadmus.geography.ports import (
    DecentralizationApiClient,
    DecentralizationApiError,
    GeographyUnitOfWorkFactory,
)

logger = logging.getLogger(__name__)

_SOURCE = "decentralization.ua"


class CommunityNotSyncedError(LookupError):
    """Raised when geometry sync is requested for an unknown community."""


@dataclass(frozen=True)
class SyncSummary:
    """One ``SyncRun`` per entity type synced by ``sync_all()``."""

    areas: SyncRun
    regions: SyncRun
    communities: SyncRun


class SyncGeographyService:
    """Orchestrates a full or partial ``decentralization.ua`` reference sync."""

    def __init__(
        self,
        unit_of_work_factory: GeographyUnitOfWorkFactory,
        client: DecentralizationApiClient,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._client = client
        self._clock = clock

    def sync_all(self) -> SyncSummary:
        areas_run = self._sync_areas()
        regions_run = self._sync_regions()
        communities_run = self._sync_communities()
        return SyncSummary(
            areas=areas_run, regions=regions_run, communities=communities_run
        )

    def sync_geometry_for_community(self, external_community_id: str) -> None:
        """Fetch and cache one community's GeoJSON geometry (AC6).

        Unlike ``sync_all()``'s best-effort entity types, this is an
        on-demand single-community call: failures propagate to the caller
        rather than being swallowed into a ``SyncRun``.
        """
        started_at = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            community = unit_of_work.geography.find_community_by_external_id(
                external_community_id
            )
            if community is None:
                raise CommunityNotSyncedError(external_community_id)

            raw = self._client.get_community_geo_json(external_community_id)
            if raw is None:
                raise CommunityNotSyncedError(external_community_id)
            geometry = parse_geo_json(raw, community.id)
            unit_of_work.geography.upsert_geometry(geometry)
            unit_of_work.geography.add_sync_run(
                SyncRun(
                    id=uuid4(),
                    entity_type=GeographyEntityType.GEOMETRY,
                    source=_SOURCE,
                    started_at=started_at,
                    status=GeographySyncStatus.SUCCEEDED,
                    records_synced=1,
                    records_failed=0,
                    completed_at=self._clock(),
                )
            )
            unit_of_work.commit()

    def _sync_areas(self) -> SyncRun:
        started_at = self._clock()
        try:
            raw_areas = self._client.list_areas()
        except DecentralizationApiError as error:
            return self._record_failed_run(GeographyEntityType.AREA, started_at, error)

        synced = 0
        failed = 0
        with self._unit_of_work_factory() as unit_of_work:
            for raw in raw_areas:
                try:
                    area = parse_area(raw, synced_at=started_at)
                except DecentralizationParseError as error:
                    logger.warning("failed to parse area: %s", error)
                    failed += 1
                    continue
                unit_of_work.geography.upsert_area(area)
                synced += 1

            run = self._build_run(GeographyEntityType.AREA, started_at, synced, failed)
            unit_of_work.geography.add_sync_run(run)
            unit_of_work.commit()
        return run

    def _sync_regions(self) -> SyncRun:
        started_at = self._clock()
        try:
            raw_regions = self._client.list_regions()
        except DecentralizationApiError as error:
            return self._record_failed_run(
                GeographyEntityType.REGION, started_at, error
            )

        synced = 0
        failed = 0
        with self._unit_of_work_factory() as unit_of_work:
            for raw in raw_regions:
                area_external_id = _flat_id(raw, "area_id")
                area = (
                    unit_of_work.geography.find_area_by_external_id(area_external_id)
                    if area_external_id
                    else None
                )
                if area is None:
                    logger.warning(
                        "skipping region %r: unknown area %r",
                        raw.get("id"),
                        area_external_id,
                    )
                    failed += 1
                    continue
                try:
                    region = parse_region(raw, area.id, synced_at=started_at)
                except DecentralizationParseError as error:
                    logger.warning("failed to parse region: %s", error)
                    failed += 1
                    continue
                unit_of_work.geography.upsert_region(region)
                synced += 1

            run = self._build_run(
                GeographyEntityType.REGION, started_at, synced, failed
            )
            unit_of_work.geography.add_sync_run(run)
            unit_of_work.commit()
        return run

    def _sync_communities(self) -> SyncRun:
        started_at = self._clock()
        try:
            raw_communities = self._client.list_communities()
        except DecentralizationApiError as error:
            return self._record_failed_run(
                GeographyEntityType.COMMUNITY, started_at, error
            )

        synced = 0
        failed = 0
        with self._unit_of_work_factory() as unit_of_work:
            for raw in raw_communities:
                area_external_id = _flat_id(raw, "area_id")
                region_external_id = _flat_id(raw, "region_id")
                area = (
                    unit_of_work.geography.find_area_by_external_id(area_external_id)
                    if area_external_id
                    else None
                )
                region = (
                    unit_of_work.geography.find_region_by_external_id(
                        region_external_id
                    )
                    if region_external_id
                    else None
                )
                if area is None or region is None:
                    logger.warning(
                        "skipping community %r: unresolved area/region",
                        raw.get("id"),
                    )
                    failed += 1
                    continue
                try:
                    community, settlements = parse_community(
                        raw, area.id, region.id, synced_at=started_at
                    )
                except DecentralizationParseError as error:
                    logger.warning("failed to parse community: %s", error)
                    failed += 1
                    continue
                unit_of_work.geography.upsert_community(community, settlements)
                synced += 1

            run = self._build_run(
                GeographyEntityType.COMMUNITY, started_at, synced, failed
            )
            unit_of_work.geography.add_sync_run(run)
            unit_of_work.commit()
        return run

    def _build_run(
        self,
        entity_type: GeographyEntityType,
        started_at: datetime,
        synced: int,
        failed: int,
    ) -> SyncRun:
        status = GeographySyncStatus.SUCCEEDED
        if failed and synced:
            status = GeographySyncStatus.PARTIAL
        elif failed and not synced:
            status = GeographySyncStatus.FAILED
        return SyncRun(
            id=uuid4(),
            entity_type=entity_type,
            source=_SOURCE,
            started_at=started_at,
            status=status,
            records_synced=synced,
            records_failed=failed,
            completed_at=self._clock(),
        )

    def _record_failed_run(
        self, entity_type: GeographyEntityType, started_at: datetime, error: Exception
    ) -> SyncRun:
        logger.error("geography sync failed for %s: %s", entity_type, error)
        run = SyncRun(
            id=uuid4(),
            entity_type=entity_type,
            source=_SOURCE,
            started_at=started_at,
            status=GeographySyncStatus.FAILED,
            records_synced=0,
            records_failed=0,
            completed_at=self._clock(),
            error_message=str(error),
        )
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.geography.add_sync_run(run)
            unit_of_work.commit()
        return run


class GeographyQueryService:
    """Read-only access to the local geography reference-data cache.

    Kept separate from ``SyncGeographyService`` so HTTP routes can never
    trigger an external sync -- they only ever read whatever was last
    successfully synced (AC15).
    """

    def __init__(self, unit_of_work_factory: GeographyUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def list_areas(self) -> list[Area]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.geography.list_areas()

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.geography.list_regions(area_id)

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.geography.list_communities(area_id, region_id)

    def get_community(self, community_id: UUID) -> Community | None:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.geography.get_community(community_id)

    def get_community_geometry(self, community_id: UUID) -> CommunityGeometry | None:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.geography.get_community_geometry(community_id)


def _flat_id(raw: dict[str, object], key: str) -> str | None:
    """Read a scalar foreign-id field (e.g. ``area_id``) as a string.

    ``decentralization.ua``'s real GraphQL schema returns these as flat
    scalars, not nested ``{id: ...}`` objects.
    """
    value = raw.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None
