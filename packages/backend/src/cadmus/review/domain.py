"""Review-queue domain objects: the cross-dictionary "awaiting review" queue.

A ``reviewer`` (or the dictionary ``owner``) works a single queue of entries
that editors have moved to :data:`~cadmus.lexicography.EntryStatus.READY_TO_REVIEW`,
across every dictionary they hold ``Permission.REVIEW`` on. Each decision --
approve (``READY_TO_REVIEW -> COMPLETE``) or send back
(``READY_TO_REVIEW -> DRAFT``) -- is recorded in an append-only
``review_events`` trail (mirrors ``lexeme_events``).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cadmus.lexicography import EntryStatus


class ReviewDecision(StrEnum):
    """One reviewer verdict on an entry awaiting review."""

    APPROVED = "approved"
    SENT_BACK = "sent_back"


@dataclass
class ReviewEvent:
    """One recorded reviewer decision (append-only audit trail).

    ``entry_id`` is intentionally not a foreign key at the infrastructure
    layer -- the trail must stay readable if the entry row is ever removed
    (same rationale as ``lexeme_events``).
    """

    id: UUID
    entry_id: UUID
    dictionary_id: UUID
    decision: ReviewDecision
    reviewer_user_id: UUID
    occurred_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class ReviewQueueItem:
    """One row of the cross-dictionary review queue."""

    entry_id: UUID
    dictionary_id: UUID
    dictionary_title: str | None
    headword: str
    status: EntryStatus
    field_count: int
    updated_at: datetime


class ReviewAccessError(LookupError):
    """Raised when the actor lacks ``Permission.REVIEW`` on the dictionary.

    Deliberately indistinguishable from "entry not found" -- an
    inaccessible dictionary never reveals that its entry exists (mirrors
    ``LexemeAccessError`` / ``EntryAccessError``).
    """

    def __init__(self, dictionary_id: UUID) -> None:
        super().__init__(f"dictionary {dictionary_id} is not accessible for review")
        self.dictionary_id = dictionary_id


class EntryNotAwaitingReviewError(ValueError):
    """Raised when approving/sending back an entry that is not READY_TO_REVIEW."""

    def __init__(self, entry_id: UUID, status: EntryStatus) -> None:
        super().__init__(f"entry {entry_id} is not awaiting review (status: {status})")
        self.entry_id = entry_id
        self.status = status
