"""SQLAlchemy persistence adapters for the review-queue module."""

from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    Uuid,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.review.domain import ReviewEvent
from cadmus.review.ports import ReviewUnitOfWorkFactory

review_registry = registry(metadata=metadata)

review_events = Table(
    "review_events",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    # Deliberately not a foreign key: the trail must survive the entry row
    # (mirrors ``lexeme_events`` -- audit history is append-oriented).
    Column("entry_id", Uuid(as_uuid=True), nullable=False, index=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("decision", String(16), nullable=False),
    Column(
        "reviewer_user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
    Column("note", Text, nullable=True),
    CheckConstraint(
        "decision IN ('approved', 'sent_back')", name="review_event_decision"
    ),
)

review_registry.map_imperatively(ReviewEvent, review_events)


class SqlAlchemyReviewEventsRepository:
    """Review-events repository backed by one caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: ReviewEvent) -> None:
        self._session.add(event)

    def list_for_entry(self, entry_id: UUID) -> list[ReviewEvent]:
        return list(
            self._session.scalars(
                select(ReviewEvent)
                .where(review_events.c.entry_id == entry_id)
                .order_by(review_events.c.occurred_at)
            )
        )


class SqlAlchemyReviewUnitOfWork:
    """Session-backed review-queue transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.review_events: SqlAlchemyReviewEventsRepository

    def __enter__(self) -> "SqlAlchemyReviewUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.review_events = SqlAlchemyReviewEventsRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("review unit of work has not been entered")
        self._session.commit()


def create_review_unit_of_work_factory(engine: Engine) -> ReviewUnitOfWorkFactory:
    """Return a zero-argument transaction factory bound to an engine."""
    return lambda: SqlAlchemyReviewUnitOfWork(engine)
