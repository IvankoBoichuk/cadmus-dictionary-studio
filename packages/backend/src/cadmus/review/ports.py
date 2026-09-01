"""Application-owned ports for review-queue infrastructure."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.review.domain import ReviewEvent


class ReviewEventsRepository(Protocol):
    """Persistence for the append-only reviewer-decision trail."""

    def add(self, event: ReviewEvent) -> None: ...

    def list_for_entry(self, entry_id: UUID) -> list[ReviewEvent]: ...


class ReviewUnitOfWork(Protocol):
    """Transaction boundary controlled by a review-queue use case."""

    @property
    def review_events(self) -> ReviewEventsRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type ReviewUnitOfWorkFactory = Callable[[], ReviewUnitOfWork]
