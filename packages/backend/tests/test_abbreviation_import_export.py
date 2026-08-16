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
    AbbreviationImportService,
    AbbreviationInput,
    AbbreviationVariant,
    Contributor,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryStatus,
    SourceFile,
    UnparsableImportFileError,
    export_abbreviations_csv,
    export_abbreviations_json,
)
from cadmus.sources.abbreviation_io import parse_abbreviations_import

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

CSV_SAMPLE = (
    "abbreviation,full_form,category,language_code,variants,note,unresolved\n"
    "розм.,розмовне,usage,uk,,,\n"
    "заст.,застаріле,usage,uk,заст;застар.,,\n"
    "??,,other,,,ще не з'ясовано,true\n"
)

JSON_SAMPLE = json.dumps(
    [
        {
            "abbreviation": "розм.",
            "full_form": "розмовне",
            "category": "usage",
            "language_code": "uk",
            "variants": [],
            "note": None,
            "unresolved": False,
        },
        {
            "abbreviation": "??",
            "full_form": None,
            "category": "other",
            "language_code": None,
            "variants": [],
            "note": "ще не з'ясовано",
            "unresolved": True,
        },
    ]
)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    abbreviations: dict[UUID, Abbreviation] = field(default_factory=dict)
    variants: dict[UUID, list[AbbreviationVariant]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def update_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by abbreviation import/export")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by abbreviation import/export")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by abbreviation import/export")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        return [
            self._with_variants(item)
            for item in self.abbreviations.values()
            if item.dictionary_id == dictionary_id
        ]

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        item = self.abbreviations.get(abbreviation_id)
        if item is None or item.dictionary_id != dictionary_id:
            return None
        return self._with_variants(item)

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        for item in self.abbreviations.values():
            if (
                item.dictionary_id == dictionary_id
                and item.category == category
                and item.language_code == language_code
                and item.abbreviation == abbreviation.strip()
                and item.id != exclude_id
            ):
                return item
        return None

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        self.abbreviations[abbreviation.id] = abbreviation

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        self.abbreviations[abbreviation.id] = abbreviation

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        self.variants[abbreviation_id] = list(variants)

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by abbreviation import/export")

    def _with_variants(self, item: Abbreviation) -> Abbreviation:
        item.variants = list(self.variants.get(item.id, []))
        return item


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


def _service(repository: MemorySourcesRepository) -> AbbreviationImportService:
    return AbbreviationImportService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: NOW,
    )


def _abbreviation(dictionary_id: UUID, **overrides: object) -> Abbreviation:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": dictionary_id,
        "abbreviation": "розм.",
        "category": AbbreviationCategory.USAGE,
        "unresolved": False,
        "created_at": NOW,
        "updated_at": NOW,
        "created_by": uuid4(),
        "updated_by": uuid4(),
        "full_form": "розмовне",
        "language_code": "uk",
    }
    defaults.update(overrides)
    return Abbreviation(**defaults)  # type: ignore[arg-type]


# --- parsing -----------------------------------------------------------------


def test_csv_parses_semicolon_separated_variants() -> None:
    rows = parse_abbreviations_import(CSV_SAMPLE.encode("utf-8"), "csv")
    assert rows[1]["variants"] == ["заст", "застар."]


def test_csv_parses_unresolved_flag() -> None:
    rows = parse_abbreviations_import(CSV_SAMPLE.encode("utf-8"), "csv")
    assert rows[2]["unresolved"] is True
    assert rows[0]["unresolved"] is False


def test_json_rejects_non_array_payload() -> None:
    with pytest.raises(UnparsableImportFileError):
        parse_abbreviations_import(b'{"not": "an array"}', "json")


def test_csv_without_header_is_rejected() -> None:
    with pytest.raises(UnparsableImportFileError):
        parse_abbreviations_import(b"", "csv")


# --- preview (AC5) -------------------------------------------------------------


def test_preview_reports_valid_and_invalid_rows() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    results = service.preview(
        dictionary.id, owner_id, CSV_SAMPLE.encode("utf-8"), "csv"
    )

    assert len(results) == 3
    assert results[0].errors == {}
    assert results[0].input is not None
    assert results[0].input.abbreviation == "розм."
    assert results[2].input is not None
    assert results[2].input.unresolved is True


def test_preview_flags_an_in_file_duplicate() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    raw = (
        "abbreviation,full_form,category,language_code,variants,note,unresolved\n"
        "розм.,розмовне,usage,uk,,,\n"
        "розм.,розмовне,usage,uk,,,\n"
    ).encode()

    results = service.preview(dictionary.id, owner_id, raw, "csv")

    assert results[0].errors == {}
    assert "abbreviation" in results[1].errors


def test_preview_flags_a_duplicate_already_in_the_dictionary() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    existing = _abbreviation(dictionary.id)
    repository.add_abbreviation(existing)
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


# --- commit (AC6) --------------------------------------------------------------


def test_commit_persists_every_valid_row() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    rows = [
        AbbreviationInput(
            abbreviation="розм.",
            category=AbbreviationCategory.USAGE,
            full_form="розмовне",
            language_code="uk",
            note=None,
            unresolved=False,
            variants=(),
        ),
        AbbreviationInput(
            abbreviation="заст.",
            category=AbbreviationCategory.USAGE,
            full_form="застаріле",
            language_code="uk",
            note=None,
            unresolved=False,
            variants=(),
        ),
    ]

    outcome = service.commit(dictionary.id, owner_id, rows)

    assert len(outcome.imported) == 2
    assert outcome.skipped == []
    assert len(repository.abbreviations) == 2


def test_commit_skips_invalid_rows_without_dropping_valid_ones() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    rows = [
        AbbreviationInput(
            abbreviation="",
            category=AbbreviationCategory.USAGE,
            full_form="X",
            language_code=None,
            note=None,
            unresolved=False,
            variants=(),
        ),
        AbbreviationInput(
            abbreviation="розм.",
            category=AbbreviationCategory.USAGE,
            full_form="розмовне",
            language_code="uk",
            note=None,
            unresolved=False,
            variants=(),
        ),
    ]

    outcome = service.commit(dictionary.id, owner_id, rows)

    assert len(outcome.imported) == 1
    assert len(outcome.skipped) == 1
    assert outcome.skipped[0].row_number == 1
    assert "abbreviation" in outcome.skipped[0].errors


def test_commit_skips_a_duplicate_already_in_the_dictionary() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_abbreviation(_abbreviation(dictionary.id))
    service = _service(repository)
    rows = [
        AbbreviationInput(
            abbreviation="розм.",
            category=AbbreviationCategory.USAGE,
            full_form="розмовне",
            language_code="uk",
            note=None,
            unresolved=False,
            variants=(),
        )
    ]

    outcome = service.commit(dictionary.id, owner_id, rows)

    assert outcome.imported == []
    assert len(outcome.skipped) == 1


def test_commit_skips_a_duplicate_within_the_same_batch() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    row = AbbreviationInput(
        abbreviation="розм.",
        category=AbbreviationCategory.USAGE,
        full_form="розмовне",
        language_code="uk",
        note=None,
        unresolved=False,
        variants=(),
    )

    outcome = service.commit(dictionary.id, owner_id, [row, row])

    assert len(outcome.imported) == 1
    assert len(outcome.skipped) == 1


# --- export (AC9) --------------------------------------------------------------


def test_json_export_round_trips_through_import() -> None:
    dictionary_id = uuid4()
    abbreviation = _abbreviation(dictionary_id, note="приклад", unresolved=False)
    abbreviation.variants = [
        AbbreviationVariant(
            id=uuid4(),
            abbreviation_id=abbreviation.id,
            variant_text="стор.",
            position=0,
        )
    ]

    exported = export_abbreviations_json([abbreviation])
    rows = parse_abbreviations_import(exported, "json")

    assert rows == [
        {
            "abbreviation": "розм.",
            "full_form": "розмовне",
            "category": "usage",
            "language_code": "uk",
            "variants": ["стор."],
            "note": "приклад",
            "unresolved": False,
        }
    ]


def test_csv_export_round_trips_through_import() -> None:
    dictionary_id = uuid4()
    abbreviation = _abbreviation(dictionary_id, unresolved=True, full_form=None)
    abbreviation.variants = [
        AbbreviationVariant(
            id=uuid4(),
            abbreviation_id=abbreviation.id,
            variant_text="стор.",
            position=0,
        ),
        AbbreviationVariant(
            id=uuid4(),
            abbreviation_id=abbreviation.id,
            variant_text="розм",
            position=1,
        ),
    ]

    exported = export_abbreviations_csv([abbreviation])
    rows = parse_abbreviations_import(exported, "csv")

    assert rows[0]["variants"] == ["стор.", "розм"]
    assert rows[0]["unresolved"] is True
    assert rows[0]["full_form"] == ""
