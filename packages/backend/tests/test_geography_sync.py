from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

import pytest
from cadmus.geography import (
    Area,
    Community,
    CommunityGeometry,
    CommunityNotSyncedError,
    DecentralizationApiUnavailableError,
    GeographyEntityType,
    GeographySyncStatus,
    Region,
    Settlement,
    SyncGeographyService,
    SyncRun,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 16, 13, 0, tzinfo=UTC)

AREA_RAW: dict[str, object] = {"id": "a1", "title": "Львівська область"}
REGION_RAW: dict[str, object] = {
    "id": "r1",
    "title": "Львівський район",
    "area_id": "a1",
}
COMMUNITY_RAW: dict[str, object] = {
    "id": "c1",
    "title": "Львівська громада",
    "katottg": "UA46000000000000000",
    "koatuu": "4610100000",
    "site": "https://example.org",
    "area_id": "a1",
    "region_id": "r1",
    "villages": [
        {"title": "Малехів", "category": "село"},
        {"title": "Рудно", "category": "село"},
    ],
    "budgets": [{"id": 1, "title": "Бюджет"}],
}


@dataclass
class FakeDecentralizationApiClient:
    areas: list[dict[str, object]] = field(default_factory=lambda: [AREA_RAW])
    regions: list[dict[str, object]] = field(default_factory=lambda: [REGION_RAW])
    communities: list[dict[str, object]] = field(
        default_factory=lambda: [COMMUNITY_RAW]
    )
    geo_json: dict[str, dict[str, object]] = field(default_factory=dict)
    fail_communities: bool = False

    def list_areas(self) -> list[dict[str, object]]:
        return self.areas

    def get_area(self, external_id: str) -> dict[str, object] | None:
        return next((a for a in self.areas if a["id"] == external_id), None)

    def list_regions(self) -> list[dict[str, object]]:
        return self.regions

    def get_region(self, external_id: str) -> dict[str, object] | None:
        return next((r for r in self.regions if r["id"] == external_id), None)

    def list_communities(self) -> list[dict[str, object]]:
        if self.fail_communities:
            raise DecentralizationApiUnavailableError("communities unreachable")
        return self.communities

    def get_community(self, external_id: str) -> dict[str, object] | None:
        return next((c for c in self.communities if c["id"] == external_id), None)

    def get_community_geo_json(self, community_id: str) -> dict[str, object] | None:
        return self.geo_json.get(community_id)


@dataclass
class MemoryGeographyRepository:
    areas: dict[UUID, Area] = field(default_factory=dict)
    regions: dict[UUID, Region] = field(default_factory=dict)
    communities: dict[UUID, Community] = field(default_factory=dict)
    settlements: dict[UUID, Settlement] = field(default_factory=dict)
    geometries: dict[UUID, CommunityGeometry] = field(default_factory=dict)
    sync_runs: list[SyncRun] = field(default_factory=list)

    def upsert_area(self, area: Area) -> None:
        existing = self.find_area_by_external_id(area.external_id)
        if existing is None:
            self.areas[area.id] = area
            return
        existing.name = area.name
        existing.last_synced_at = area.last_synced_at

    def upsert_region(self, region: Region) -> None:
        existing = self.find_region_by_external_id(region.external_id)
        if existing is None:
            self.regions[region.id] = region
            return
        existing.name = region.name
        existing.area_id = region.area_id
        existing.last_synced_at = region.last_synced_at

    def upsert_community(
        self, community: Community, settlements: Sequence[Settlement]
    ) -> None:
        existing = self.find_community_by_external_id(community.external_id)
        if existing is None:
            self.communities[community.id] = community
            community_id = community.id
        else:
            existing.name = community.name
            existing.area_id = community.area_id
            existing.region_id = community.region_id
            existing.katottg = community.katottg
            existing.koatuu = community.koatuu
            existing.last_synced_at = community.last_synced_at
            community_id = existing.id

        existing_keys = {
            (s.title, s.category): s.id
            for s in self.settlements.values()
            if s.community_id == community_id
        }
        incoming_keys = set()
        for settlement in settlements:
            key = (settlement.title, settlement.category)
            incoming_keys.add(key)
            if key in existing_keys:
                continue
            self.settlements[settlement.id] = settlement

        for key, settlement_id in existing_keys.items():
            if key not in incoming_keys:
                del self.settlements[settlement_id]

    def upsert_geometry(self, geometry: CommunityGeometry) -> None:
        self.geometries[geometry.community_id] = geometry

    def find_area_by_external_id(self, external_id: str) -> Area | None:
        return next(
            (a for a in self.areas.values() if a.external_id == external_id), None
        )

    def find_region_by_external_id(self, external_id: str) -> Region | None:
        return next(
            (r for r in self.regions.values() if r.external_id == external_id), None
        )

    def find_community_by_external_id(self, external_id: str) -> Community | None:
        return next(
            (c for c in self.communities.values() if c.external_id == external_id),
            None,
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
        raise AssertionError("not used by sync service")

    def list_areas(self) -> list[Area]:
        raise AssertionError("not used by sync service")

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        raise AssertionError("not used by sync service")

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
        raise AssertionError("not used by sync service")

    def get_area(self, area_id: UUID) -> Area | None:
        raise AssertionError("not used by sync service")

    def get_region(self, region_id: UUID) -> Region | None:
        raise AssertionError("not used by sync service")

    def get_settlement(self, settlement_id: UUID) -> Settlement | None:
        raise AssertionError("not used by sync service")

    def get_community(self, community_id: UUID) -> Community | None:
        return self.communities.get(community_id)

    def get_community_geometry(self, community_id: UUID) -> CommunityGeometry | None:
        return self.geometries.get(community_id)

    def add_sync_run(self, run: SyncRun) -> None:
        self.sync_runs.append(run)


class MemoryGeographyUnitOfWork:
    def __init__(self, repository: MemoryGeographyRepository) -> None:
        self.geography = repository
        self.committed = False

    def __enter__(self) -> "MemoryGeographyUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True


def _service(
    repository: MemoryGeographyRepository,
    client: FakeDecentralizationApiClient,
    clock: datetime = NOW,
) -> SyncGeographyService:
    return SyncGeographyService(
        unit_of_work_factory=lambda: MemoryGeographyUnitOfWork(repository),
        client=client,
        clock=lambda: clock,
    )


def test_sync_all_populates_areas_regions_communities_settlements() -> None:
    repository = MemoryGeographyRepository()
    service = _service(repository, FakeDecentralizationApiClient())

    summary = service.sync_all()

    assert summary.areas.status == GeographySyncStatus.SUCCEEDED
    assert summary.regions.status == GeographySyncStatus.SUCCEEDED
    assert summary.communities.status == GeographySyncStatus.SUCCEEDED
    assert len(repository.areas) == 1
    assert len(repository.regions) == 1
    assert len(repository.communities) == 1
    assert len(repository.settlements) == 2

    (area,) = repository.areas.values()
    (region,) = repository.regions.values()
    (community,) = repository.communities.values()
    assert region.area_id == area.id
    assert community.area_id == area.id
    assert community.region_id == region.id
    assert all(s.community_id == community.id for s in repository.settlements.values())


def test_sync_all_is_idempotent_and_bumps_last_synced_at() -> None:
    repository = MemoryGeographyRepository()
    service = _service(repository, FakeDecentralizationApiClient(), clock=NOW)
    service.sync_all()

    (area_before,) = repository.areas.values()
    (community_before,) = repository.communities.values()
    settlement_ids_before = set(repository.settlements)

    service_later = _service(repository, FakeDecentralizationApiClient(), clock=LATER)
    service_later.sync_all()

    assert len(repository.areas) == 1
    assert len(repository.regions) == 1
    assert len(repository.communities) == 1
    (area_after,) = repository.areas.values()
    (community_after,) = repository.communities.values()
    assert area_after.id == area_before.id
    assert community_after.id == community_before.id
    assert area_after.last_synced_at == LATER
    # Settlement ids are stable across resync (diff-based upsert).
    assert set(repository.settlements) == settlement_ids_before


def test_region_with_unknown_area_is_skipped_not_fatal() -> None:
    repository = MemoryGeographyRepository()
    bad_region: dict[str, object] = {
        "id": "r2",
        "title": "Orphan",
        "area_id": "unknown",
    }
    client = FakeDecentralizationApiClient(regions=[REGION_RAW, bad_region])
    service = _service(repository, client)

    summary = service.sync_all()

    assert summary.regions.status == GeographySyncStatus.PARTIAL
    assert summary.regions.records_synced == 1
    assert summary.regions.records_failed == 1
    assert len(repository.regions) == 1


def test_communities_api_failure_leaves_areas_and_regions_committed() -> None:
    repository = MemoryGeographyRepository()
    client = FakeDecentralizationApiClient(fail_communities=True)
    service = _service(repository, client)

    summary = service.sync_all()

    assert summary.areas.status == GeographySyncStatus.SUCCEEDED
    assert summary.regions.status == GeographySyncStatus.SUCCEEDED
    assert summary.communities.status == GeographySyncStatus.FAILED
    assert summary.communities.error_message is not None
    assert len(repository.areas) == 1
    assert len(repository.regions) == 1
    assert len(repository.communities) == 0

    entity_types = {run.entity_type for run in repository.sync_runs}
    assert entity_types == {
        GeographyEntityType.AREA,
        GeographyEntityType.REGION,
        GeographyEntityType.COMMUNITY,
    }


def test_sync_geometry_for_community_happy_path() -> None:
    repository = MemoryGeographyRepository()
    client = FakeDecentralizationApiClient()
    service = _service(repository, client)
    service.sync_all()
    (community,) = repository.communities.values()

    client.geo_json["c1"] = {
        "type": "Point",
        "coordinates": [24.03, 49.84],
    }
    service.sync_geometry_for_community("c1")

    geometry = repository.geometries[community.id]
    assert geometry.geometry_type == "Point"
    assert geometry.community_id == community.id


def test_sync_geometry_for_unknown_community_raises() -> None:
    repository = MemoryGeographyRepository()
    service = _service(repository, FakeDecentralizationApiClient())

    with pytest.raises(CommunityNotSyncedError):
        service.sync_geometry_for_community("does-not-exist")
