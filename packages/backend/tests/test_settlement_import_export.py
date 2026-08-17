import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
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
    DictionarySettlementMapping,
    DictionaryStatus,
    SettlementMappingImportService,
    SettlementMappingStatus,
    SourceFile,
    UnparsableImportFileError,
    export_settlement_mappings_csv,
    export_settlement_mappings_json,
    parse_settlement_mappings_import,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

CSV_SAMPLE = (
    "source_label,source_note,modern_settlement_name,settlement_category\n"
    "Іванівка,,,\n"
    "Петрівка,стара назва,Петрівське,село\n"
)

JSON_SAMPLE = json.dumps(
    [
        {
            "source_label": "Іванівка",
            "source_note": None,
            "modern_settlement_name": None,
            "settlement_category": None,
        },
        {
            "source_label": "Петрівка",
            "source_note": "стара назва",
            "modern_settlement_name": "Петрівське",
            "settlement_category": "село",
        },
    ]
)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    mappings: dict[UUID, DictionarySettlementMapping] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by settlement import/export")

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError("not used by settlement import/export")

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by settlement import/export")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by settlement import/export")

    def update_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by settlement import/export")

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by settlement import/export")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by settlement import/export")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by settlement import/export")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by settlement import/export")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by settlement import/export")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by settlement import/export")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by settlement import/export")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by settlement import/export")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by settlement import/export")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by settlement import/export")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by settlement import/export")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by settlement import/export")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by settlement import/export")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by settlement import/export")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by settlement import/export")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        return [
            item
            for item in self.mappings.values()
            if item.dictionary_id == dictionary_id
        ]

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
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        for item in self.mappings.values():
            if (
                item.dictionary_id == dictionary_id
                and item.source_label == source_label_key
                and item.id != exclude_id
            ):
                return item
        return None

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        self.mappings[mapping.id] = mapping

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        self.mappings[mapping.id] = mapping

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by settlement import/export")


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = repository
        self.committed = False

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
        self.committed = True


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.CONFIGURED,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _service(repository: MemorySourcesRepository) -> SettlementMappingImportService:
    return SettlementMappingImportService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: NOW,
    )


def _mapping(dictionary_id: UUID, **overrides: object) -> DictionarySettlementMapping:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": dictionary_id,
        "source_label": "Іванівка",
        "status": SettlementMappingStatus.UNRESOLVED,
        "created_at": NOW,
        "updated_at": NOW,
        "created_by": uuid4(),
        "updated_by": uuid4(),
    }
    defaults.update(overrides)
    return DictionarySettlementMapping(**defaults)  # type: ignore[arg-type]


# --- parsing -----------------------------------------------------------------


def test_csv_parses_rows() -> None:
    rows = parse_settlement_mappings_import(CSV_SAMPLE.encode("utf-8"), "csv")
    assert rows[1]["source_label"] == "Петрівка"
    assert rows[1]["modern_settlement_name"] == "Петрівське"


def test_json_rejects_non_array_payload() -> None:
    with pytest.raises(UnparsableImportFileError):
        parse_settlement_mappings_import(b'{"not": "an array"}', "json")


def test_csv_without_header_is_rejected() -> None:
    with pytest.raises(UnparsableImportFileError):
        parse_settlement_mappings_import(b"", "csv")


# --- preview (AC7, BH-48) -------------------------------------------------------


def test_preview_reports_valid_rows() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    results = service.preview(
        dictionary.id, owner_id, CSV_SAMPLE.encode("utf-8"), "csv"
    )

    assert len(results) == 2
    assert results[0].errors == {}
    assert results[0].input is not None
    assert results[0].input.source_label == "Іванівка"
    assert results[0].input.status is SettlementMappingStatus.UNRESOLVED


def test_preview_flags_a_row_missing_a_source_label() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    raw = b"source_label,source_note,modern_settlement_name,settlement_category\n,,,\n"

    results = service.preview(dictionary.id, owner_id, raw, "csv")

    assert "source_label" in results[0].errors


def test_preview_flags_an_in_file_duplicate() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    raw = (
        "source_label,source_note,modern_settlement_name,settlement_category\n"
        "Іванівка,,,\n"
        "Іванівка,,,\n"
    ).encode()

    results = service.preview(dictionary.id, owner_id, raw, "csv")

    assert results[0].errors == {}
    assert "source_label" in results[1].errors


def test_preview_flags_a_duplicate_already_in_the_dictionary() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    existing = _mapping(dictionary.id)
    repository.add_settlement_mapping(existing)
    service = _service(repository)

    results = service.preview(
        dictionary.id, owner_id, JSON_SAMPLE.encode("utf-8"), "json"
    )

    assert results[0].duplicate_of == existing.id
    assert results[1].duplicate_of is None


def test_preview_of_a_missing_dictionary_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.preview(uuid4(), uuid4(), CSV_SAMPLE.encode("utf-8"), "csv")


# --- commit (AC7) ----------------------------------------------------------------


def test_commit_persists_every_valid_row_as_unresolved() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    rows = service.preview(dictionary.id, owner_id, CSV_SAMPLE.encode("utf-8"), "csv")
    inputs = [row.input for row in rows if row.input is not None]

    outcome = service.commit(dictionary.id, owner_id, inputs)

    assert len(outcome.imported) == 2
    assert outcome.skipped == []
    assert all(
        item.status is SettlementMappingStatus.UNRESOLVED for item in outcome.imported
    )


def test_commit_skips_a_duplicate_already_in_the_dictionary() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_settlement_mapping(_mapping(dictionary.id))
    service = _service(repository)
    rows = service.preview(dictionary.id, owner_id, JSON_SAMPLE.encode("utf-8"), "json")
    inputs = [row.input for row in rows if row.input is not None]

    outcome = service.commit(dictionary.id, owner_id, inputs)

    assert len(outcome.imported) == 1
    assert len(outcome.skipped) == 1


def test_commit_of_a_missing_dictionary_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.commit(uuid4(), uuid4(), [])


# --- export ----------------------------------------------------------------------


def test_json_export_round_trips_through_import() -> None:
    dictionary_id = uuid4()
    mapping = _mapping(
        dictionary_id,
        source_note="уточнення",
        modern_settlement_name="Петрівське",
        settlement_category="село",
        status=SettlementMappingStatus.CONFIRMED,
        area_name="Львівська область",
        region_name="Львівський район",
        community_name="Львівська громада",
        external_community_id="community-1",
        katottg="UA46060000000000000",
        koatuu="4610100000",
    )

    exported = export_settlement_mappings_json([mapping])
    rows = parse_settlement_mappings_import(exported, "json")

    assert rows == [
        {
            "source_label": "Іванівка",
            "source_note": "уточнення",
            "modern_settlement_name": "Петрівське",
            "settlement_category": "село",
            "status": "confirmed",
            "area_name": "Львівська область",
            "region_name": "Львівський район",
            "community_name": "Львівська громада",
            "external_community_id": "community-1",
            "katottg": "UA46060000000000000",
            "koatuu": "4610100000",
        }
    ]


def test_csv_export_round_trips_through_import() -> None:
    dictionary_id = uuid4()
    mapping = _mapping(dictionary_id, modern_settlement_name=None)

    exported = export_settlement_mappings_csv([mapping])
    rows = parse_settlement_mappings_import(exported, "csv")

    assert rows[0]["source_label"] == "Іванівка"
    assert rows[0]["modern_settlement_name"] == ""
    assert rows[0]["status"] == "unresolved"
