"""Post-scanning dictionary status: domain rule + the two sources services."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.sources import (
    AdvanceDictionaryProcessingStatusService,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryEventType,
    DictionaryNotProcessedError,
    DictionaryStatus,
    ProcessingSignals,
    PublishDictionaryService,
    SourcesRepository,
)
from cadmus.sources.domain import next_processing_status

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _signals(
    *,
    has_any_lexeme: bool = False,
    has_processing_work: bool = False,
    all_lexemes_complete: bool = False,
    all_entries_complete: bool = True,
) -> ProcessingSignals:
    return ProcessingSignals(
        has_any_lexeme=has_any_lexeme,
        has_processing_work=has_processing_work,
        all_lexemes_complete=all_lexemes_complete,
        all_entries_complete=all_entries_complete,
    )


@pytest.mark.parametrize(
    ("current", "signals", "expected"),
    [
        (
            DictionaryStatus.DRAFT,
            _signals(has_any_lexeme=True, all_lexemes_complete=True),
            DictionaryStatus.DRAFT,
        ),
        (
            DictionaryStatus.CONFIGURED,
            _signals(has_processing_work=True),
            DictionaryStatus.CONFIGURED,
        ),
        (
            DictionaryStatus.PUBLISHED,
            _signals(has_processing_work=True),
            DictionaryStatus.PUBLISHED,
        ),
        (DictionaryStatus.SCANNED, _signals(), DictionaryStatus.SCANNED),
        (
            DictionaryStatus.SCANNED,
            _signals(has_any_lexeme=True, has_processing_work=True),
            DictionaryStatus.IN_PROGRESS,
        ),
        (
            DictionaryStatus.IN_PROGRESS,
            _signals(
                has_any_lexeme=True,
                has_processing_work=True,
                all_lexemes_complete=True,
                all_entries_complete=True,
            ),
            DictionaryStatus.PROCESSED,
        ),
        (
            DictionaryStatus.PROCESSED,
            _signals(has_any_lexeme=True, has_processing_work=True),
            DictionaryStatus.IN_PROGRESS,
        ),
        (
            DictionaryStatus.PROCESSED,
            _signals(),
            DictionaryStatus.SCANNED,
        ),
    ],
)
def test_next_processing_status(
    current: DictionaryStatus,
    signals: ProcessingSignals,
    expected: DictionaryStatus,
) -> None:
    assert next_processing_status(current, signals) == expected


@dataclass
class MemorySourcesRepository:
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


def _dictionary(owner_id: UUID, status: DictionaryStatus) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=status,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _advance_service(
    repository: MemorySourcesRepository,
) -> AdvanceDictionaryProcessingStatusService:
    return AdvanceDictionaryProcessingStatusService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: NOW,
    )


def _publish_service(
    repository: MemorySourcesRepository,
) -> PublishDictionaryService:
    return PublishDictionaryService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: NOW,
    )


def test_advance_persists_the_move_and_audit_event() -> None:
    owner_id = uuid4()
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id, DictionaryStatus.SCANNED)
    repository.dictionaries[dictionary.id] = dictionary

    result = _advance_service(repository).advance(
        dictionary.id,
        owner_id,
        _signals(has_any_lexeme=True, has_processing_work=True),
    )

    assert result.status == DictionaryStatus.IN_PROGRESS
    assert repository.dictionaries[dictionary.id].status == DictionaryStatus.IN_PROGRESS
    (event,) = repository.events
    assert event.event_type == DictionaryEventType.STATUS_CHANGED
    assert event.previous_status == DictionaryStatus.SCANNED
    assert event.new_status == DictionaryStatus.IN_PROGRESS


def test_advance_is_a_noop_when_the_target_is_unchanged() -> None:
    owner_id = uuid4()
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id, DictionaryStatus.PUBLISHED)
    repository.dictionaries[dictionary.id] = dictionary

    result = _advance_service(repository).advance(
        dictionary.id, owner_id, _signals(has_processing_work=True)
    )

    assert result.status == DictionaryStatus.PUBLISHED
    assert repository.events == []


def test_advance_by_non_owner_raises_access_error() -> None:
    owner_id = uuid4()
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id, DictionaryStatus.SCANNED)
    repository.dictionaries[dictionary.id] = dictionary

    with pytest.raises(DictionaryAccessError):
        _advance_service(repository).advance(
            dictionary.id, uuid4(), _signals(has_processing_work=True)
        )


def test_publish_moves_processed_to_published_with_an_event() -> None:
    owner_id = uuid4()
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id, DictionaryStatus.PROCESSED)
    repository.dictionaries[dictionary.id] = dictionary

    result = _publish_service(repository).publish(dictionary.id, owner_id)

    assert result.status == DictionaryStatus.PUBLISHED
    (event,) = repository.events
    assert event.previous_status == DictionaryStatus.PROCESSED
    assert event.new_status == DictionaryStatus.PUBLISHED


def test_publish_rejects_a_dictionary_that_is_not_processed() -> None:
    owner_id = uuid4()
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id, DictionaryStatus.IN_PROGRESS)
    repository.dictionaries[dictionary.id] = dictionary

    with pytest.raises(DictionaryNotProcessedError):
        _publish_service(repository).publish(dictionary.id, owner_id)
    assert repository.dictionaries[dictionary.id].status == DictionaryStatus.IN_PROGRESS


def test_publish_is_idempotent_on_an_already_published_dictionary() -> None:
    owner_id = uuid4()
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id, DictionaryStatus.PUBLISHED)
    repository.dictionaries[dictionary.id] = dictionary

    result = _publish_service(repository).publish(dictionary.id, owner_id)

    assert result.status == DictionaryStatus.PUBLISHED
    assert repository.events == []
