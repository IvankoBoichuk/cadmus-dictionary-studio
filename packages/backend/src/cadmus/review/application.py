"""Review-queue application use cases: the cross-dictionary review queue."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.access import AuthorizationService, Permission
from cadmus.lexicography import (
    DictionaryEntry,
    EntryAccessError,
    EntryStatus,
    EntryValidationError,
    LexicographyUnitOfWorkFactory,
    ValidateEntryService,
)
from cadmus.review.domain import (
    EntryNotAwaitingReviewError,
    ReviewAccessError,
    ReviewDecision,
    ReviewEvent,
    ReviewQueueItem,
)
from cadmus.review.ports import ReviewUnitOfWorkFactory
from cadmus.sources import Dictionary, DictionaryAccessError, GetDictionaryService


class ReviewService:
    """Work the cross-dictionary "awaiting review" queue for one actor.

    Composes existing bounded contexts (the same way ``ScanProgressService``
    combines ``sources`` + ``lexicography``): access is resolved through
    ``GetDictionaryService`` with ``Permission.REVIEW``; the set of
    reviewable dictionaries is owned-plus-reviewer-membership; entries are
    read and their status changed through the ``lexicography`` unit of
    work; schema validation reuses ``ValidateEntryService.validate``.
    """

    def __init__(
        self,
        review_unit_of_work_factory: ReviewUnitOfWorkFactory,
        lexicography_unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_service: GetDictionaryService,
        authorization: AuthorizationService,
        validate_service: ValidateEntryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._review_unit_of_work_factory = review_unit_of_work_factory
        self._lexicography_unit_of_work_factory = lexicography_unit_of_work_factory
        self._dictionary_service = dictionary_service
        self._authorization = authorization
        self._validate_service = validate_service
        self._clock = clock

    def list_queue(self, actor_id: UUID) -> list[ReviewQueueItem]:
        """Every ``READY_TO_REVIEW`` entry the actor may review, oldest first."""
        dictionaries = self._reviewable_dictionaries(actor_id)
        if not dictionaries:
            return []

        with self._lexicography_unit_of_work_factory() as unit_of_work:
            entries = unit_of_work.lexicography.list_entries_awaiting_review(
                list(dictionaries)
            )
            field_counts: dict[UUID, int] = {}
            for dictionary_id in dictionaries:
                field_counts.update(
                    unit_of_work.lexicography.count_fields_by_entry(dictionary_id)
                )

        items = [
            ReviewQueueItem(
                entry_id=entry.id,
                dictionary_id=entry.dictionary_id,
                dictionary_title=dictionaries[entry.dictionary_id].title,
                headword=entry.headword,
                status=entry.status,
                field_count=field_counts.get(entry.id, 0),
                updated_at=entry.updated_at,
            )
            for entry in entries
            if entry.dictionary_id in dictionaries
        ]
        items.sort(key=lambda item: item.updated_at)
        return items

    def approve(
        self, entry_id: UUID, actor_id: UUID, note: str | None = None
    ) -> DictionaryEntry:
        """Sign an entry off: ``READY_TO_REVIEW -> COMPLETE`` (schema-gated)."""
        return self._decide(entry_id, actor_id, ReviewDecision.APPROVED, note)

    def send_back(
        self, entry_id: UUID, actor_id: UUID, note: str | None = None
    ) -> DictionaryEntry:
        """Return an entry to its editor: ``READY_TO_REVIEW -> DRAFT``."""
        return self._decide(entry_id, actor_id, ReviewDecision.SENT_BACK, note)

    def _decide(
        self,
        entry_id: UUID,
        actor_id: UUID,
        decision: ReviewDecision,
        note: str | None,
    ) -> DictionaryEntry:
        with self._lexicography_unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
        if entry is None:
            raise EntryAccessError(entry_id)

        dictionary_id = entry.dictionary_id
        try:
            self._dictionary_service.get(
                dictionary_id, actor_id, required_permission=Permission.REVIEW
            )
        except DictionaryAccessError as error:
            raise ReviewAccessError(dictionary_id) from error

        if entry.status is not EntryStatus.READY_TO_REVIEW:
            raise EntryNotAwaitingReviewError(entry_id, entry.status)

        if decision is ReviewDecision.APPROVED:
            errors = self._validate_service.validate(entry_id)
            if errors:
                raise EntryValidationError(errors)
            new_status = EntryStatus.COMPLETE
        else:
            new_status = EntryStatus.DRAFT

        now = self._clock()
        with self._lexicography_unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
            if entry is None:
                raise EntryAccessError(entry_id)
            entry.status = new_status
            entry.updated_at = now
            entry.updated_by = actor_id
            unit_of_work.lexicography.update_entry(entry)
            unit_of_work.commit()

        with self._review_unit_of_work_factory() as unit_of_work:
            unit_of_work.review_events.add(
                ReviewEvent(
                    id=uuid4(),
                    entry_id=entry_id,
                    dictionary_id=dictionary_id,
                    decision=decision,
                    reviewer_user_id=actor_id,
                    occurred_at=now,
                    note=note,
                )
            )
            unit_of_work.commit()
        return entry

    def _reviewable_dictionaries(self, actor_id: UUID) -> dict[UUID, Dictionary]:
        """Dictionaries the actor holds ``Permission.REVIEW`` on (owner + reviewer)."""
        result: dict[UUID, Dictionary] = {
            entry.dictionary.id: entry.dictionary
            for entry in self._dictionary_service.list_for_owner(actor_id)
        }
        for dictionary_id in self._authorization.list_reviewer_dictionary_ids(actor_id):
            if dictionary_id in result:
                continue
            try:
                result[dictionary_id] = self._dictionary_service.get(
                    dictionary_id, actor_id, required_permission=Permission.REVIEW
                )
            except DictionaryAccessError:
                continue
        return result
