from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.geography.domain import Area, Community, Region, Settlement
from cadmus.sources import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    Contributor,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryPageRange,
    DictionarySettlementMapping,
    DictionaryStatus,
    SettlementConfirmationService,
    SettlementMappingAccessError,
    SettlementMappingStatus,
    SettlementMappingValidationError,
    SourceFile,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

_UNUSED = "not used by settlement confirmation"


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    mappings: dict[UUID, DictionarySettlementMapping] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError(_UNUSED)

    def add_dictionary(self, dictionary: Dictionary) -> None:
        raise AssertionError(_UNUSED)

    def update_dictionary(self, dictionary: Dictionary) -> None:
        raise AssertionError(_UNUSED)

    def add_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError(_UNUSED)

    def update_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError(_UNUSED)

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError(_UNUSED)

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError(_UNUSED)

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError(_UNUSED)

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError(_UNUSED)

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError(_UNUSED)

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError(_UNUSED)

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        raise AssertionError(_UNUSED)

    def list_pages(self, source_file_id: UUID) -> list[DictionaryPage]:
        raise AssertionError(_UNUSED)

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError(_UNUSED)

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError(_UNUSED)

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError(_UNUSED)

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError(_UNUSED)

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError(_UNUSED)

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError(_UNUSED)

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError(_UNUSED)

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError(_UNUSED)

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        item = self.mappings.get(mapping_id)
        if item is None or item.dictionary_id != dictionary_id:
            return None
        return item

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError(_UNUSED)

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError(_UNUSED)

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        self.mappings[mapping.id] = mapping

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        raise AssertionError(_UNUSED)

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None:
        raise AssertionError(_UNUSED)


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = repository

    def __enter__(self) -> "MemorySourcesUnitOfWork":
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


@dataclass
class MemoryGeographyRepository:
    settlements: dict[UUID, Settlement] = field(default_factory=dict)
    communities: dict[UUID, Community] = field(default_factory=dict)
    regions: dict[UUID, Region] = field(default_factory=dict)
    areas: dict[UUID, Area] = field(default_factory=dict)

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
        return self.areas.get(area_id)

    def get_region(self, region_id: UUID) -> Region | None:
        return self.regions.get(region_id)

    def get_settlement(self, settlement_id: UUID) -> Settlement | None:
        return self.settlements.get(settlement_id)

    def list_areas(self) -> list[Area]:
        raise AssertionError(_UNUSED)

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        raise AssertionError(_UNUSED)

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
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
        raise AssertionError(_UNUSED)

    def get_community(self, community_id: UUID) -> Community | None:
        return self.communities.get(community_id)

    def get_community_geometry(self, community_id: UUID) -> None:
        raise AssertionError(_UNUSED)

    def add_sync_run(self, run: object) -> None:
        raise AssertionError(_UNUSED)


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


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.CONFIGURED,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _mapping(
    dictionary_id: UUID, owner_id: UUID, *, settlement_id: UUID | None
) -> DictionarySettlementMapping:
    return DictionarySettlementMapping(
        id=uuid4(),
        dictionary_id=dictionary_id,
        source_label="Іванівка",
        status=SettlementMappingStatus.SUGGESTED,
        created_at=NOW,
        updated_at=NOW,
        created_by=owner_id,
        updated_by=owner_id,
        settlement_id=settlement_id,
    )


def _full_hierarchy() -> tuple[Settlement, Community, Region, Area]:
    area = Area(
        id=uuid4(), external_id="a1", name="Львівська область", last_synced_at=NOW
    )
    region = Region(
        id=uuid4(),
        external_id="r1",
        name="Львівський район",
        area_id=area.id,
        last_synced_at=NOW,
    )
    community = Community(
        id=uuid4(),
        external_id="c1",
        name="Львівська громада",
        area_id=area.id,
        region_id=region.id,
        katottg="UA46000000000000000",
        koatuu="4610100000",
        last_synced_at=NOW,
    )
    settlement = Settlement(
        id=uuid4(), community_id=community.id, title="Іванівка", category="село"
    )
    return settlement, community, region, area


def _service(
    sources_repository: MemorySourcesRepository,
    geography_repository: MemoryGeographyRepository,
    clock: datetime = NOW,
) -> SettlementConfirmationService:
    return SettlementConfirmationService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(sources_repository),
        geography_unit_of_work_factory=lambda: MemoryGeographyUnitOfWork(
            geography_repository
        ),
        clock=lambda: clock,
    )


def test_confirm_snapshots_current_hierarchy() -> None:
    owner_id = uuid4()
    sources_repository = MemorySourcesRepository()
    geography_repository = MemoryGeographyRepository()
    dictionary = _dictionary(owner_id)
    sources_repository.dictionaries[dictionary.id] = dictionary

    settlement, community, region, area = _full_hierarchy()
    geography_repository.settlements[settlement.id] = settlement
    geography_repository.communities[community.id] = community
    geography_repository.regions[region.id] = region
    geography_repository.areas[area.id] = area

    mapping = _mapping(dictionary.id, owner_id, settlement_id=settlement.id)
    sources_repository.mappings[mapping.id] = mapping

    service = _service(sources_repository, geography_repository)
    confirmed = service.confirm(dictionary.id, mapping.id, owner_id)

    assert confirmed.status is SettlementMappingStatus.CONFIRMED
    assert confirmed.confirmed_by == owner_id
    assert confirmed.confirmed_at == NOW
    assert confirmed.area_name == area.name
    assert confirmed.region_name == region.name
    assert confirmed.community_name == community.name
    assert confirmed.external_community_id == community.external_id
    assert confirmed.katottg == community.katottg
    assert confirmed.koatuu == community.koatuu
    assert confirmed.settlement_category == settlement.category


def test_confirm_without_settlement_id_is_rejected() -> None:
    owner_id = uuid4()
    sources_repository = MemorySourcesRepository()
    geography_repository = MemoryGeographyRepository()
    dictionary = _dictionary(owner_id)
    sources_repository.dictionaries[dictionary.id] = dictionary

    mapping = _mapping(dictionary.id, owner_id, settlement_id=None)
    sources_repository.mappings[mapping.id] = mapping

    service = _service(sources_repository, geography_repository)
    with pytest.raises(SettlementMappingValidationError) as error:
        service.confirm(dictionary.id, mapping.id, owner_id)
    assert "settlement_id" in error.value.errors


def test_confirm_missing_settlement_in_geography_is_rejected() -> None:
    owner_id = uuid4()
    sources_repository = MemorySourcesRepository()
    geography_repository = MemoryGeographyRepository()
    dictionary = _dictionary(owner_id)
    sources_repository.dictionaries[dictionary.id] = dictionary

    mapping = _mapping(dictionary.id, owner_id, settlement_id=uuid4())
    sources_repository.mappings[mapping.id] = mapping

    service = _service(sources_repository, geography_repository)
    with pytest.raises(SettlementMappingValidationError) as error:
        service.confirm(dictionary.id, mapping.id, owner_id)
    assert "settlement_id" in error.value.errors


def test_confirm_missing_mapping_raises_access_error() -> None:
    owner_id = uuid4()
    sources_repository = MemorySourcesRepository()
    geography_repository = MemoryGeographyRepository()
    dictionary = _dictionary(owner_id)
    sources_repository.dictionaries[dictionary.id] = dictionary

    service = _service(sources_repository, geography_repository)
    with pytest.raises(SettlementMappingAccessError):
        service.confirm(dictionary.id, uuid4(), owner_id)


def test_confirm_by_non_owner_raises_access_error() -> None:
    owner_id = uuid4()
    stranger_id = uuid4()
    sources_repository = MemorySourcesRepository()
    geography_repository = MemoryGeographyRepository()
    dictionary = _dictionary(owner_id)
    sources_repository.dictionaries[dictionary.id] = dictionary

    mapping = _mapping(dictionary.id, owner_id, settlement_id=uuid4())
    sources_repository.mappings[mapping.id] = mapping

    service = _service(sources_repository, geography_repository)
    with pytest.raises(DictionaryAccessError):
        service.confirm(dictionary.id, mapping.id, stranger_id)


def test_confirmed_by_and_confirmed_at_are_server_derived() -> None:
    owner_id = uuid4()
    sources_repository = MemorySourcesRepository()
    geography_repository = MemoryGeographyRepository()
    dictionary = _dictionary(owner_id)
    sources_repository.dictionaries[dictionary.id] = dictionary

    settlement, community, region, area = _full_hierarchy()
    geography_repository.settlements[settlement.id] = settlement
    geography_repository.communities[community.id] = community
    geography_repository.regions[region.id] = region
    geography_repository.areas[area.id] = area

    mapping = _mapping(dictionary.id, owner_id, settlement_id=settlement.id)
    sources_repository.mappings[mapping.id] = mapping

    confirmed_at = datetime(2026, 8, 16, 15, 30, tzinfo=UTC)
    service = _service(sources_repository, geography_repository, clock=confirmed_at)
    confirmed = service.confirm(dictionary.id, mapping.id, owner_id)

    assert confirmed.confirmed_by == owner_id
    assert confirmed.confirmed_at == confirmed_at
