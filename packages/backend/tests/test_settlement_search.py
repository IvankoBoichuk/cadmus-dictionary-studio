from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

from cadmus.geography.domain import Area, Community, Region, Settlement
from cadmus.sources import SettlementSearchService

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

_UNUSED = "not used by settlement search"


@dataclass
class MemoryGeographyRepository:
    rows: list[tuple[Settlement, Community]] = field(default_factory=list)
    last_call: dict[str, object] | None = None

    def upsert_area(self, area: Area) -> None:
        raise AssertionError(_UNUSED)

    def upsert_region(self, region: Region) -> None:
        raise AssertionError(_UNUSED)

    def upsert_community(
        self, community: Community, settlements: Sequence[Settlement]
    ) -> None:
        raise AssertionError(_UNUSED)

    def upsert_geometry(self, geometry: object) -> None:
        raise AssertionError(_UNUSED)

    def find_area_by_external_id(self, external_id: str) -> Area | None:
        raise AssertionError(_UNUSED)

    def find_region_by_external_id(self, external_id: str) -> Region | None:
        raise AssertionError(_UNUSED)

    def find_community_by_external_id(self, external_id: str) -> Community | None:
        raise AssertionError(_UNUSED)

    def get_area(self, area_id: UUID) -> Area | None:
        raise AssertionError(_UNUSED)

    def get_region(self, region_id: UUID) -> Region | None:
        raise AssertionError(_UNUSED)

    def get_settlement(self, settlement_id: UUID) -> Settlement | None:
        raise AssertionError(_UNUSED)

    def list_areas(self) -> list[Area]:
        raise AssertionError(_UNUSED)

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        raise AssertionError(_UNUSED)

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
        raise AssertionError(_UNUSED)

    def get_community(self, community_id: UUID) -> Community | None:
        raise AssertionError(_UNUSED)

    def get_community_geometry(self, community_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def add_sync_run(self, run: object) -> None:
        raise AssertionError(_UNUSED)

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
        self.last_call = {
            "query": query,
            "area_id": area_id,
            "region_id": region_id,
            "community_id": community_id,
            "category": category,
            "limit": limit,
        }
        results = self.rows
        if query:
            results = [row for row in results if query.lower() in row[0].title.lower()]
        if area_id is not None:
            results = [row for row in results if row[1].area_id == area_id]
        if region_id is not None:
            results = [row for row in results if row[1].region_id == region_id]
        if community_id is not None:
            results = [row for row in results if row[1].id == community_id]
        if category:
            results = [row for row in results if row[0].category == category]
        return results


class MemoryGeographyUnitOfWork:
    def __init__(self, repository: MemoryGeographyRepository) -> None:
        self.geography = repository

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
        pass


def _row(
    *, title: str, category: str, area_id: UUID, region_id: UUID
) -> tuple[Settlement, Community]:
    community_id = uuid4()
    community = Community(
        id=community_id,
        external_id=str(community_id),
        name="Тестова громада",
        area_id=area_id,
        region_id=region_id,
        last_synced_at=NOW,
    )
    settlement = Settlement(
        id=uuid4(), community_id=community_id, title=title, category=category
    )
    return settlement, community


def _service(repository: MemoryGeographyRepository) -> SettlementSearchService:
    return SettlementSearchService(
        geography_unit_of_work_factory=lambda: MemoryGeographyUnitOfWork(repository)
    )


def test_search_returns_flattened_suggestions() -> None:
    area_id = uuid4()
    region_id = uuid4()
    row = _row(title="Іванівка", category="село", area_id=area_id, region_id=region_id)
    repository = MemoryGeographyRepository(rows=[row])
    service = _service(repository)

    results = service.search(
        query="Іван", area_id=None, region_id=None, community_id=None, category=None
    )

    assert len(results) == 1
    suggestion = results[0]
    settlement, community = row
    assert suggestion.settlement_id == settlement.id
    assert suggestion.title == settlement.title
    assert suggestion.category == settlement.category
    assert suggestion.community_id == community.id
    assert suggestion.community_name == community.name
    assert suggestion.region_id == community.region_id
    assert suggestion.area_id == community.area_id


def test_search_passes_filters_through() -> None:
    area_id = uuid4()
    region_id = uuid4()
    repository = MemoryGeographyRepository(rows=[])
    service = _service(repository)

    service.search(
        query="Петр",
        area_id=area_id,
        region_id=region_id,
        community_id=None,
        category="місто",
    )

    assert repository.last_call == {
        "query": "Петр",
        "area_id": area_id,
        "region_id": region_id,
        "community_id": None,
        "category": "місто",
        "limit": 25,
    }


def test_search_filters_out_non_matching_category() -> None:
    area_id = uuid4()
    region_id = uuid4()
    village = _row(
        title="Іванівка", category="село", area_id=area_id, region_id=region_id
    )
    town = _row(
        title="Петрівка", category="місто", area_id=area_id, region_id=region_id
    )
    repository = MemoryGeographyRepository(rows=[village, town])
    service = _service(repository)

    results = service.search(
        query=None, area_id=None, region_id=None, community_id=None, category="місто"
    )

    assert len(results) == 1
    assert results[0].title == "Петрівка"
