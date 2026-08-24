"""BH-58: finish-scanning-stage domain and application behavior."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    DictionaryNotReadyToScanError,
    FinishScanningService,
    Lexeme,
    LexemeAccessError,
    LexemeEvent,
    LexemeOrigin,
    LexicographyRepository,
)
from cadmus.sources import (
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryEventType,
    DictionaryStatus,
    GetDictionaryService,
    MarkDictionaryScannedService,
    SourcesRepository,
)

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    """A minimal fake covering only what these BH-58 services need."""

    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    events: list[DictionaryEvent] = field(default_factory=list)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_event(self, event: DictionaryEvent) -> None:
        self.events.append(event)


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = cast(SourcesRepository, repository)

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
class MemoryLexicographyRepository:
    lexemes: dict[UUID, Lexeme] = field(default_factory=dict)
    events: list[LexemeEvent] = field(default_factory=list)

    def has_any_lexeme(self, dictionary_id: UUID) -> bool:
        return any(
            lexeme.dictionary_id == dictionary_id for lexeme in self.lexemes.values()
        )


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
        self.lexicography = cast(LexicographyRepository, repository)

    def __enter__(self) -> "MemoryLexicographyUnitOfWork":
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


def _dictionary(
    owner_id: UUID, status: DictionaryStatus = DictionaryStatus.CONFIGURED
) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=status,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _lexeme(dictionary_id: UUID) -> Lexeme:
    return Lexeme(
        id=uuid4(),
        dictionary_id=dictionary_id,
        page_id=uuid4(),
        source_text="слово",
        x=10,
        y=10,
        width=100,
        height=40,
        origin=LexemeOrigin.MANUAL,
        created_at=NOW,
        created_by=uuid4(),
        updated_at=NOW,
        updated_by=uuid4(),
    )


class Fixture:
    def __init__(self, status: DictionaryStatus = DictionaryStatus.CONFIGURED) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id, status)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.scanning_service = MarkDictionaryScannedService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.service = FinishScanningService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            scanning_service=self.scanning_service,
        )

    def add_lexeme(self) -> None:
        lexeme = _lexeme(self.dictionary.id)
        self.lexicography_repository.lexemes[lexeme.id] = lexeme


# -- MarkDictionaryScannedService (sources) -----------------------------------


def test_mark_scanned_transitions_a_configured_dictionary() -> None:
    fixture = Fixture(status=DictionaryStatus.CONFIGURED)

    updated = fixture.scanning_service.mark_scanned(
        fixture.dictionary.id, fixture.owner_id
    )

    assert updated.status == DictionaryStatus.SCANNED


def test_mark_scanned_records_a_status_changed_event() -> None:
    fixture = Fixture(status=DictionaryStatus.CONFIGURED)

    fixture.scanning_service.mark_scanned(fixture.dictionary.id, fixture.owner_id)

    assert len(fixture.sources_repository.events) == 1
    event = fixture.sources_repository.events[0]
    assert event.event_type is DictionaryEventType.STATUS_CHANGED
    assert event.previous_status is DictionaryStatus.CONFIGURED
    assert event.new_status is DictionaryStatus.SCANNED


def test_mark_scanned_is_idempotent_on_repeated_calls() -> None:
    fixture = Fixture(status=DictionaryStatus.CONFIGURED)

    fixture.scanning_service.mark_scanned(fixture.dictionary.id, fixture.owner_id)
    fixture.scanning_service.mark_scanned(fixture.dictionary.id, fixture.owner_id)

    assert fixture.dictionary.status == DictionaryStatus.SCANNED
    assert len(fixture.sources_repository.events) == 1


def test_mark_scanned_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(DictionaryAccessError):
        fixture.scanning_service.mark_scanned(fixture.dictionary.id, uuid4())


# -- FinishScanningService (lexicography) --------------------------------------


def test_finish_transitions_to_scanned_once_a_lexeme_exists() -> None:
    fixture = Fixture()
    fixture.add_lexeme()

    dictionary = fixture.service.finish(fixture.dictionary.id, fixture.owner_id)

    assert dictionary.status == DictionaryStatus.SCANNED


def test_finish_without_any_lexeme_raises_not_ready() -> None:
    fixture = Fixture()

    with pytest.raises(DictionaryNotReadyToScanError):
        fixture.service.finish(fixture.dictionary.id, fixture.owner_id)

    assert fixture.dictionary.status == DictionaryStatus.CONFIGURED


def test_finish_is_idempotent_and_does_not_recheck_lexemes() -> None:
    fixture = Fixture(status=DictionaryStatus.SCANNED)
    # Deliberately no lexemes: an already-scanned dictionary must not be
    # re-validated (e.g. after every lexeme was later deleted).

    dictionary = fixture.service.finish(fixture.dictionary.id, fixture.owner_id)

    assert dictionary.status == DictionaryStatus.SCANNED
    assert fixture.sources_repository.events == []


def test_finish_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()
    fixture.add_lexeme()

    with pytest.raises(LexemeAccessError):
        fixture.service.finish(fixture.dictionary.id, uuid4())


def test_finish_missing_dictionary_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.finish(uuid4(), fixture.owner_id)
