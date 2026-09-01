"""Cross-dictionary review queue: approve / send-back use cases."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.access import (
    AuthorizationService,
    MembershipsRepository,
    ProjectMembership,
    Role,
)
from cadmus.lexicography import (
    DictionaryEntry,
    EntryAccessError,
    EntryStatus,
    EntryValidationError,
    LexicographyRepository,
    ValidateEntryService,
)
from cadmus.review import (
    EntryNotAwaitingReviewError,
    ReviewAccessError,
    ReviewDecision,
    ReviewEvent,
    ReviewEventsRepository,
    ReviewService,
)
from cadmus.sources import (
    Dictionary,
    DictionaryStatus,
    GetDictionaryService,
    SourcesRepository,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


# --- fakes ------------------------------------------------------------------


@dataclass
class MemoryMembershipsRepository:
    memberships: dict[tuple[UUID, UUID], ProjectMembership] = field(
        default_factory=dict
    )

    def get_membership(
        self, dictionary_id: UUID, user_id: UUID
    ) -> ProjectMembership | None:
        return self.memberships.get((dictionary_id, user_id))

    def list_memberships_for_user(self, user_id: UUID) -> list[ProjectMembership]:
        return [m for (_, uid), m in self.memberships.items() if uid == user_id]


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        return [d for d in self.dictionaries.values() if d.owner_id == owner_id]

    def get_source_file(self, dictionary_id: UUID) -> None:
        return None

    def list_page_ranges(self, dictionary_id: UUID) -> list[object]:
        return []


@dataclass
class MemoryLexicographyRepository:
    entries: dict[UUID, DictionaryEntry] = field(default_factory=dict)
    field_counts: dict[UUID, int] = field(default_factory=dict)

    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None:
        return self.entries.get(entry_id)

    def update_entry(self, entry: DictionaryEntry) -> None:
        self.entries[entry.id] = entry

    def list_entries_awaiting_review(
        self, dictionary_ids: list[UUID]
    ) -> list[DictionaryEntry]:
        ids = set(dictionary_ids)
        return sorted(
            (
                e
                for e in self.entries.values()
                if e.dictionary_id in ids and e.status is EntryStatus.READY_TO_REVIEW
            ),
            key=lambda e: e.updated_at,
        )

    def count_fields_by_entry(self, dictionary_id: UUID) -> dict[UUID, int]:
        return {
            e.id: self.field_counts.get(e.id, 0)
            for e in self.entries.values()
            if e.dictionary_id == dictionary_id
        }


@dataclass
class MemoryReviewEventsRepository:
    events: list[ReviewEvent] = field(default_factory=list)

    def add(self, event: ReviewEvent) -> None:
        self.events.append(event)

    def list_for_entry(self, entry_id: UUID) -> list[ReviewEvent]:
        return [e for e in self.events if e.entry_id == entry_id]


def _noop_exit(
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: TracebackType | None,
) -> None:
    return None


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = cast(SourcesRepository, repository)

    def __enter__(self) -> "MemorySourcesUnitOfWork":
        return self

    __exit__ = staticmethod(_noop_exit)

    def commit(self) -> None:
        pass


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
        self.lexicography = cast(LexicographyRepository, repository)

    def __enter__(self) -> "MemoryLexicographyUnitOfWork":
        return self

    __exit__ = staticmethod(_noop_exit)

    def commit(self) -> None:
        pass


class MemoryMembershipsUnitOfWork:
    def __init__(self, repository: MemoryMembershipsRepository) -> None:
        self.memberships = cast(MembershipsRepository, repository)

    def __enter__(self) -> "MemoryMembershipsUnitOfWork":
        return self

    __exit__ = staticmethod(_noop_exit)

    def commit(self) -> None:
        pass


class MemoryReviewUnitOfWork:
    def __init__(self, repository: MemoryReviewEventsRepository) -> None:
        self.review_events = cast(ReviewEventsRepository, repository)

    def __enter__(self) -> "MemoryReviewUnitOfWork":
        return self

    __exit__ = staticmethod(_noop_exit)

    def commit(self) -> None:
        pass


class _StubValidateService:
    """Stand-in for ``ValidateEntryService`` with a controllable verdict."""

    def __init__(self, errors: dict[str, str] | None = None) -> None:
        self._errors = errors or {}

    def validate(self, entry_id: UUID) -> dict[str, str]:
        return dict(self._errors)


# --- helpers --------------------------------------------------------------


def _dictionary(owner_id: UUID, title: str = "Словник") -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
        title=title,
    )


def _entry(
    dictionary_id: UUID,
    *,
    status: EntryStatus = EntryStatus.READY_TO_REVIEW,
    headword: str = "слово",
    updated_at: datetime = NOW,
) -> DictionaryEntry:
    return DictionaryEntry(
        id=uuid4(),
        dictionary_id=dictionary_id,
        lexeme_id=uuid4(),
        headword=headword,
        status=status,
        created_at=NOW,
        updated_at=updated_at,
        created_by=uuid4(),
        updated_by=uuid4(),
        schema_id=uuid4(),
    )


@dataclass
class _World:
    service: ReviewService
    lexicography: MemoryLexicographyRepository
    sources: MemorySourcesRepository
    memberships: MemoryMembershipsRepository
    review_events: MemoryReviewEventsRepository


def _make_world(*, validate_errors: dict[str, str] | None = None) -> _World:
    sources = MemorySourcesRepository()
    memberships = MemoryMembershipsRepository()
    lexicography = MemoryLexicographyRepository()
    review_events = MemoryReviewEventsRepository()

    authorization = AuthorizationService(
        membership_unit_of_work_factory=lambda: MemoryMembershipsUnitOfWork(memberships)
    )
    dictionary_service = GetDictionaryService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(sources),
        authorization=authorization,
    )
    service = ReviewService(
        review_unit_of_work_factory=lambda: MemoryReviewUnitOfWork(review_events),
        lexicography_unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
            lexicography
        ),
        dictionary_service=dictionary_service,
        authorization=authorization,
        validate_service=cast(
            ValidateEntryService, _StubValidateService(validate_errors)
        ),
        clock=lambda: NOW,
    )
    return _World(service, lexicography, sources, memberships, review_events)


def _add_membership(
    world: _World, dictionary_id: UUID, user_id: UUID, role: Role
) -> None:
    world.memberships.memberships[(dictionary_id, user_id)] = ProjectMembership(
        id=uuid4(),
        dictionary_id=dictionary_id,
        user_id=user_id,
        role=role,
        created_at=NOW,
        created_by=user_id,
        updated_at=NOW,
        updated_by=user_id,
    )


# --- tests --------------------------------------------------------------


def test_queue_spans_owned_and_reviewer_dictionaries_only() -> None:
    world = _make_world()
    owner = uuid4()
    reviewer = uuid4()

    owned = _dictionary(reviewer, title="Власний")
    reviewed = _dictionary(owner, title="Рецензований")
    edited_only = _dictionary(owner, title="Лише редагування")
    for d in (owned, reviewed, edited_only):
        world.sources.dictionaries[d.id] = d
    _add_membership(world, reviewed.id, reviewer, Role.REVIEWER)
    _add_membership(world, edited_only.id, reviewer, Role.EDITOR)

    e_owned = _entry(owned.id, headword="owned-new", updated_at=NOW)
    e_reviewed = _entry(
        reviewed.id,
        headword="reviewed-old",
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    e_hidden = _entry(edited_only.id, headword="editor-only")
    e_done = _entry(owned.id, headword="already-done", status=EntryStatus.COMPLETE)
    for e in (e_owned, e_reviewed, e_hidden, e_done):
        world.lexicography.entries[e.id] = e
    world.lexicography.field_counts[e_owned.id] = 3

    queue = world.service.list_queue(reviewer)

    # oldest-updated first, editor-only + completed entries excluded
    assert [item.headword for item in queue] == ["reviewed-old", "owned-new"]
    assert {item.dictionary_title for item in queue} == {"Власний", "Рецензований"}
    assert next(i for i in queue if i.headword == "owned-new").field_count == 3


def test_approve_marks_entry_complete_and_records_event() -> None:
    world = _make_world()
    reviewer = uuid4()
    d = _dictionary(reviewer)
    world.sources.dictionaries[d.id] = d
    entry = _entry(d.id)
    world.lexicography.entries[entry.id] = entry

    result = world.service.approve(entry.id, reviewer, note="Гарна стаття")

    assert result.status is EntryStatus.COMPLETE
    assert world.lexicography.entries[entry.id].status is EntryStatus.COMPLETE
    assert world.lexicography.entries[entry.id].updated_by == reviewer
    (event,) = world.review_events.events
    assert event.decision is ReviewDecision.APPROVED
    assert event.note == "Гарна стаття"
    assert event.reviewer_user_id == reviewer


def test_approve_blocked_when_entry_fails_schema() -> None:
    world = _make_world(validate_errors={"meaning": "Відсутнє значення."})
    reviewer = uuid4()
    d = _dictionary(reviewer)
    world.sources.dictionaries[d.id] = d
    entry = _entry(d.id)
    world.lexicography.entries[entry.id] = entry

    with pytest.raises(EntryValidationError):
        world.service.approve(entry.id, reviewer)

    assert world.lexicography.entries[entry.id].status is EntryStatus.READY_TO_REVIEW
    assert world.review_events.events == []


def test_send_back_returns_entry_to_draft_with_note() -> None:
    world = _make_world()
    reviewer = uuid4()
    d = _dictionary(reviewer)
    world.sources.dictionaries[d.id] = d
    entry = _entry(d.id)
    world.lexicography.entries[entry.id] = entry

    result = world.service.send_back(entry.id, reviewer, note="Виправте приклади")

    assert result.status is EntryStatus.DRAFT
    (event,) = world.review_events.events
    assert event.decision is ReviewDecision.SENT_BACK
    assert event.note == "Виправте приклади"


def test_decision_rejected_when_entry_not_awaiting_review() -> None:
    world = _make_world()
    reviewer = uuid4()
    d = _dictionary(reviewer)
    world.sources.dictionaries[d.id] = d
    entry = _entry(d.id, status=EntryStatus.DRAFT)
    world.lexicography.entries[entry.id] = entry

    with pytest.raises(EntryNotAwaitingReviewError):
        world.service.approve(entry.id, reviewer)
    with pytest.raises(EntryNotAwaitingReviewError):
        world.service.send_back(entry.id, reviewer)


def test_decision_denied_without_review_permission() -> None:
    world = _make_world()
    owner = uuid4()
    outsider = uuid4()
    d = _dictionary(owner)
    world.sources.dictionaries[d.id] = d
    _add_membership(world, d.id, outsider, Role.EDITOR)
    entry = _entry(d.id)
    world.lexicography.entries[entry.id] = entry

    with pytest.raises(ReviewAccessError):
        world.service.approve(entry.id, outsider)


def test_decision_on_unknown_entry_raises_entry_access_error() -> None:
    world = _make_world()
    with pytest.raises(EntryAccessError):
        world.service.approve(uuid4(), uuid4())
