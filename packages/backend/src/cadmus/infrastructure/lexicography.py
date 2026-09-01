"""SQLAlchemy persistence adapters for the lexicography module."""

from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.lexicography.domain import (
    ArticleSchema,
    DictionaryEntry,
    EntryField,
    EntryFragment,
    EntryStatus,
    Lexeme,
    LexemeEvent,
    LexemeStatus,
)
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
    Column("x2", Float, nullable=True),
    Column("y2", Float, nullable=True),
    Column("width2", Float, nullable=True),
    Column("height2", Float, nullable=True),
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
    Column(
        "status",
        String(20),
        nullable=False,
        default=LexemeStatus.DRAFT.value,
        server_default=LexemeStatus.DRAFT.value,
    ),
    CheckConstraint("origin IN ('manual', 'ocr')", name="lexeme_origin"),
    CheckConstraint(
        "status IN ('draft', 'ready_to_process', 'ready_to_review', 'complete')",
        name="lexeme_status",
    ),
    CheckConstraint("width > 0 AND height > 0", name="lexeme_positive_size"),
    CheckConstraint(
        "(x2 IS NULL) = (y2 IS NULL) AND (y2 IS NULL) = (width2 IS NULL) "
        "AND (width2 IS NULL) = (height2 IS NULL)",
        name="lexeme_second_box_all_or_none",
    ),
    CheckConstraint(
        "width2 IS NULL OR (width2 > 0 AND height2 > 0)",
        name="lexeme_second_box_positive_size",
    ),
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

article_schemas = Table(
    "article_schemas",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("version", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("source_description", Text, nullable=False),
    Column("definition", JSONB, nullable=False),
    Column("raw_provider_response", JSONB, nullable=True),
    Column("provider_name", String(255), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("presentation_formula", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("activated_at", DateTime(timezone=True), nullable=True),
    Column(
        "activated_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=True,
    ),
    CheckConstraint(
        "status IN ('pending', 'running', 'ready', 'failed')",
        name="article_schema_status",
    ),
    UniqueConstraint(
        "dictionary_id", "version", name="uq_article_schemas_dictionary_version"
    ),
)

dictionary_entries = Table(
    "dictionary_entries",
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
        "lexeme_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.lexemes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("headword", String(500), nullable=False),
    Column("status", String(20), nullable=False),
    Column(
        "schema_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.article_schemas.id", ondelete="SET NULL"),
        nullable=True,
    ),
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
    CheckConstraint(
        "status IN ('draft', 'ready_to_review', 'complete')",
        name="dictionary_entry_status",
    ),
)

entry_fragments = Table(
    "entry_fragments",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "entry_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_entries.id", ondelete="CASCADE"),
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
    Column("x", Float, nullable=False),
    Column("y", Float, nullable=False),
    Column("width", Float, nullable=False),
    Column("height", Float, nullable=False),
    Column("x2", Float, nullable=True),
    Column("y2", Float, nullable=True),
    Column("width2", Float, nullable=True),
    Column("height2", Float, nullable=True),
    Column("reading_order", Integer, nullable=False),
    Column("recognized_text", Text, nullable=False),
    CheckConstraint("width > 0 AND height > 0", name="entry_fragment_positive_size"),
)

entry_fields = Table(
    "entry_fields",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "entry_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "fragment_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.entry_fragments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "parent_field_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.entry_fields.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    Column("field_path", String(500), nullable=False),
    Column("role", String(32), nullable=False),
    Column("position", Integer, nullable=False),
    Column("source_text", Text, nullable=False),
    Column("normalized_text", Text, nullable=True),
    Column("confidence", Float, nullable=True),
    Column("origin", String(16), nullable=False),
    Column("processing_run_id", Uuid(as_uuid=True), nullable=True),
    Column("source_start", Integer, nullable=True),
    Column("source_end", Integer, nullable=True),
    Column("x", Float, nullable=True),
    Column("y", Float, nullable=True),
    Column("width", Float, nullable=True),
    Column("height", Float, nullable=True),
    Column(
        "settlement_mapping_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_settlement_mappings.id", ondelete="SET NULL"),
        nullable=True,
    ),
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
    CheckConstraint(
        "role IN ('headword', 'part_of_speech', 'meaning', 'example', 'synonym', "
        "'abbreviation', 'geographic_label', 'other')",
        name="entry_field_role",
    ),
    CheckConstraint("origin IN ('model', 'rule', 'manual')", name="entry_field_origin"),
    CheckConstraint("source_end >= source_start", name="entry_field_positive_span"),
)

lexicography_registry.map_imperatively(Lexeme, lexemes)
lexicography_registry.map_imperatively(LexemeEvent, lexeme_events)
lexicography_registry.map_imperatively(ArticleSchema, article_schemas)
lexicography_registry.map_imperatively(DictionaryEntry, dictionary_entries)
lexicography_registry.map_imperatively(EntryFragment, entry_fragments)
lexicography_registry.map_imperatively(EntryField, entry_fields)


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

    def count_lexemes_by_status(self, dictionary_id: UUID) -> dict[LexemeStatus, int]:
        rows = self._session.execute(
            select(lexemes.c.status, func.count())
            .where(lexemes.c.dictionary_id == dictionary_id)
            .group_by(lexemes.c.status)
        )
        return {LexemeStatus(status): count for status, count in rows}

    def count_entries_by_status(self, dictionary_id: UUID) -> dict[EntryStatus, int]:
        rows = self._session.execute(
            select(dictionary_entries.c.status, func.count())
            .where(dictionary_entries.c.dictionary_id == dictionary_id)
            .group_by(dictionary_entries.c.status)
        )
        return {EntryStatus(status): count for status, count in rows}

    def add_article_schema(self, schema: ArticleSchema) -> None:
        self._session.add(schema)

    def get_article_schema(self, schema_id: UUID) -> ArticleSchema | None:
        return self._session.get(ArticleSchema, schema_id)

    def get_active_article_schema(self, dictionary_id: UUID) -> ArticleSchema | None:
        return self._session.scalar(
            select(ArticleSchema)
            .where(
                article_schemas.c.dictionary_id == dictionary_id,
                article_schemas.c.activated_at.is_not(None),
            )
            .order_by(article_schemas.c.activated_at.desc())
            .limit(1)
        )

    def list_article_schemas(self, dictionary_id: UUID) -> list[ArticleSchema]:
        return list(
            self._session.scalars(
                select(ArticleSchema)
                .where(article_schemas.c.dictionary_id == dictionary_id)
                .order_by(article_schemas.c.version)
            )
        )

    def update_article_schema(self, schema: ArticleSchema) -> None:
        self._session.add(schema)

    def add_entry(self, entry: DictionaryEntry) -> None:
        self._session.add(entry)

    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None:
        return self._session.get(DictionaryEntry, entry_id)

    def get_entry_by_lexeme(self, lexeme_id: UUID) -> DictionaryEntry | None:
        return self._session.scalar(
            select(DictionaryEntry).where(dictionary_entries.c.lexeme_id == lexeme_id)
        )

    def list_entries_for_dictionary(self, dictionary_id: UUID) -> list[DictionaryEntry]:
        return list(
            self._session.scalars(
                select(DictionaryEntry)
                .where(dictionary_entries.c.dictionary_id == dictionary_id)
                .order_by(
                    dictionary_entries.c.headword,
                    dictionary_entries.c.created_at,
                )
            )
        )

    def list_entries_awaiting_review(
        self, dictionary_ids: list[UUID]
    ) -> list[DictionaryEntry]:
        if not dictionary_ids:
            return []
        return list(
            self._session.scalars(
                select(DictionaryEntry)
                .where(
                    dictionary_entries.c.dictionary_id.in_(dictionary_ids),
                    dictionary_entries.c.status == EntryStatus.READY_TO_REVIEW.value,
                )
                .order_by(dictionary_entries.c.updated_at)
            )
        )

    def count_fields_by_entry(self, dictionary_id: UUID) -> dict[UUID, int]:
        rows = self._session.execute(
            select(entry_fields.c.entry_id, func.count())
            .join(
                dictionary_entries,
                entry_fields.c.entry_id == dictionary_entries.c.id,
            )
            .where(dictionary_entries.c.dictionary_id == dictionary_id)
            .group_by(entry_fields.c.entry_id)
        )
        return {entry_id: count for entry_id, count in rows}

    def update_entry(self, entry: DictionaryEntry) -> None:
        self._session.add(entry)

    def add_fragment(self, fragment: EntryFragment) -> None:
        self._session.add(fragment)

    def list_fragments_for_entry(self, entry_id: UUID) -> list[EntryFragment]:
        return list(
            self._session.scalars(
                select(EntryFragment)
                .where(entry_fragments.c.entry_id == entry_id)
                .order_by(entry_fragments.c.reading_order)
            )
        )

    def add_field(self, field: EntryField) -> None:
        self._session.add(field)

    def list_fields_for_entry(self, entry_id: UUID) -> list[EntryField]:
        return list(
            self._session.scalars(
                select(EntryField)
                .where(entry_fields.c.entry_id == entry_id)
                .order_by(entry_fields.c.position)
            )
        )

    def update_field(self, field: EntryField) -> None:
        self._session.add(field)

    def delete_field(self, field_id: UUID) -> None:
        self._session.execute(delete(entry_fields).where(entry_fields.c.id == field_id))


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
