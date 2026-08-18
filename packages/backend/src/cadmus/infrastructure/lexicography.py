"""SQLAlchemy persistence adapters for the lexicography module."""

from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Table,
    Uuid,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.lexicography.domain import Lexeme, LexemeEvent
from cadmus.lexicography.ports import LexicographyUnitOfWorkFactory

lexicography_registry = registry(metadata=metadata)

lexemes = Table(
    "lexemes",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "page_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("source_text", String(500), nullable=False),
    Column("x", Float, nullable=False),
    Column("y", Float, nullable=False),
    Column("width", Float, nullable=False),
    Column("height", Float, nullable=False),
    Column("origin", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column(
        "updated_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    CheckConstraint("origin IN ('manual', 'ocr')", name="lexeme_origin"),
    CheckConstraint("width > 0 AND height > 0", name="lexeme_positive_size"),
)

lexeme_events = Table(
    "lexeme_events",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("lexeme_id", Uuid(as_uuid=True), nullable=False, index=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("event_type", String(16), nullable=False),
    Column(
        "actor_user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
    Column("changed_fields", JSONB, nullable=False, default=list),
    CheckConstraint("event_type IN ('updated', 'deleted')", name="lexeme_event_type"),
)

lexicography_registry.map_imperatively(Lexeme, lexemes)
lexicography_registry.map_imperatively(LexemeEvent, lexeme_events)


class SqlAlchemyLexicographyRepository:
    """Lexicography repository backed by one caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_lexeme(self, lexeme: Lexeme) -> None:
        self._session.add(lexeme)

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]:
        return list(
            self._session.scalars(
                select(Lexeme)
                .where(lexemes.c.page_id == page_id)
                .order_by(lexemes.c.created_at)
            )
        )

    def get_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> Lexeme | None:
        lexeme = self._session.get(Lexeme, lexeme_id)
        if lexeme is None or lexeme.dictionary_id != dictionary_id:
            return None
        return lexeme

    def update_lexeme(self, lexeme: Lexeme) -> None:
        self._session.add(lexeme)

    def delete_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> None:
        self._session.execute(
            delete(lexemes).where(
                lexemes.c.id == lexeme_id,
                lexemes.c.dictionary_id == dictionary_id,
            )
        )

    def add_lexeme_event(self, event: LexemeEvent) -> None:
        self._session.add(event)

    def list_page_ids_with_lexemes(self, dictionary_id: UUID) -> set[UUID]:
        return set(
            self._session.scalars(
                select(lexemes.c.page_id)
                .where(lexemes.c.dictionary_id == dictionary_id)
                .distinct()
            )
        )

    def has_any_lexeme(self, dictionary_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(lexemes.c.id)
                .where(lexemes.c.dictionary_id == dictionary_id)
                .limit(1)
            )
            is not None
        )


class SqlAlchemyLexicographyUnitOfWork:
    """Session-backed lexicography transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.lexicography: SqlAlchemyLexicographyRepository

    def __enter__(self) -> "SqlAlchemyLexicographyUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.lexicography = SqlAlchemyLexicographyRepository(self._session)
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
            raise RuntimeError("lexicography unit of work has not been entered")
        self._session.commit()


def create_lexicography_unit_of_work_factory(
    engine: Engine,
) -> LexicographyUnitOfWorkFactory:
    """Return a zero-argument transaction factory bound to an engine."""
    return lambda: SqlAlchemyLexicographyUnitOfWork(engine)
