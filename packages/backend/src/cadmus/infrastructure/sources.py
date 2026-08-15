"""SQLAlchemy persistence adapters for the sources module."""

from collections.abc import Sequence
from types import TracebackType
from typing import BinaryIO
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Uuid,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.sources.domain import (
    Contributor,
    Dictionary,
    DictionaryEvent,
    DictionaryLanguage,
    SourceFile,
)
from cadmus.sources.ports import InvalidPdfError, SourcesUnitOfWorkFactory

sources_registry = registry(metadata=metadata)

dictionaries = Table(
    "dictionaries",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "owner_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("status", String(32), nullable=False),
    Column("title", String(512), nullable=True),
    Column("description", Text, nullable=True),
    Column("dictionary_type", String(255), nullable=True),
    Column("publisher", String(255), nullable=True),
    Column("publication_year", Integer, nullable=True),
    Column("edition", String(255), nullable=True),
    Column("isbn", String(20), nullable=True),
    Column("digital_source", String(500), nullable=True),
    Column("legal_status", String(32), nullable=True),
    Column("license_type", String(255), nullable=True),
    Column("permission_reference", String(500), nullable=True),
    Column("rights_note", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column(
        "updated_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    CheckConstraint("status IN ('draft', 'configured')", name="dictionary_status"),
    CheckConstraint(
        "legal_status IS NULL OR legal_status IN "
        "('public_domain', 'licensed', 'permission_granted', 'restricted', "
        "'unknown')",
        name="dictionary_legal_status",
    ),
)

dictionary_contributors = Table(
    "dictionary_contributors",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(255), nullable=False),
    Column("role", String(16), nullable=False),
    Column("position", Integer, nullable=False),
    CheckConstraint("role IN ('author', 'compiler')", name="contributor_role"),
)

dictionary_languages = Table(
    "dictionary_languages",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("language_code", String(2), nullable=False),
    Column("position", Integer, nullable=False),
)

dictionary_source_files = Table(
    "dictionary_source_files",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("original_filename", String(255), nullable=False),
    Column("mime_type", String(100), nullable=False),
    Column("byte_size", BigInteger, nullable=False),
    Column("page_count", Integer, nullable=True),
    Column("checksum_sha256", String(64), nullable=False, index=True),
    Column("storage_key", String(500), nullable=False, unique=True),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column(
        "uploaded_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("inspection_status", String(16), nullable=False),
    Column("inspection_error", Text, nullable=True),
    CheckConstraint(
        "inspection_status IN ('pending', 'verified', 'failed')",
        name="source_file_inspection_status",
    ),
)

dictionary_events = Table(
    "dictionary_events",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("event_type", String(32), nullable=False),
    Column(
        "actor_user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id"),
        nullable=False,
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
    Column("changed_fields", JSONB, nullable=False, default=list),
    CheckConstraint(
        "event_type IN ('created', 'source_uploaded', 'metadata_updated')",
        name="dictionary_event_type",
    ),
)

sources_registry.map_imperatively(Dictionary, dictionaries)
sources_registry.map_imperatively(Contributor, dictionary_contributors)
sources_registry.map_imperatively(DictionaryLanguage, dictionary_languages)
sources_registry.map_imperatively(SourceFile, dictionary_source_files)
sources_registry.map_imperatively(DictionaryEvent, dictionary_events)


class SqlAlchemySourcesRepository:
    """Sources repository backed by one caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        dictionary = self._session.get(Dictionary, dictionary_id)
        if dictionary is None:
            return None
        dictionary.contributors = list(
            self._session.scalars(
                select(Contributor)
                .where(dictionary_contributors.c.dictionary_id == dictionary_id)
                .order_by(dictionary_contributors.c.position)
            )
        )
        dictionary.languages = list(
            self._session.scalars(
                select(DictionaryLanguage)
                .where(dictionary_languages.c.dictionary_id == dictionary_id)
                .order_by(dictionary_languages.c.position)
            )
        )
        return dictionary

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self._session.scalar(
            select(SourceFile).where(
                dictionary_source_files.c.dictionary_id == dictionary_id
            )
        )

    def get_source_file_by_id(self, source_file_id: UUID) -> SourceFile | None:
        return self._session.get(SourceFile, source_file_id)

    def find_duplicate_source(
        self, owner_id: UUID, checksum_sha256: str
    ) -> Dictionary | None:
        statement = (
            select(Dictionary)
            .join(
                dictionary_source_files,
                dictionary_source_files.c.dictionary_id == dictionaries.c.id,
            )
            .where(
                dictionaries.c.owner_id == owner_id,
                dictionary_source_files.c.checksum_sha256 == checksum_sha256,
            )
        )
        return self._session.scalars(statement).first()

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self._session.add(dictionary)

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self._session.add(dictionary)

    def add_source_file(self, source_file: SourceFile) -> None:
        self._session.add(source_file)

    def update_source_file(self, source_file: SourceFile) -> None:
        self._session.add(source_file)

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        self._session.execute(
            delete(dictionary_contributors).where(
                dictionary_contributors.c.dictionary_id == dictionary_id
            )
        )
        for contributor in contributors:
            self._session.add(contributor)

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        self._session.execute(
            delete(dictionary_languages).where(
                dictionary_languages.c.dictionary_id == dictionary_id
            )
        )
        for language in languages:
            self._session.add(language)

    def add_event(self, event: DictionaryEvent) -> None:
        self._session.add(event)


class SqlAlchemySourcesUnitOfWork:
    """Session-backed sources transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.sources: SqlAlchemySourcesRepository

    def __enter__(self) -> "SqlAlchemySourcesUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.sources = SqlAlchemySourcesRepository(self._session)
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
            raise RuntimeError("sources unit of work has not been entered")
        self._session.commit()


def create_sources_unit_of_work_factory(
    engine: Engine,
) -> SourcesUnitOfWorkFactory:
    """Return a zero-argument transaction factory bound to an engine."""
    return lambda: SqlAlchemySourcesUnitOfWork(engine)


class PyPdfInspector:
    """Bounded, defensive PDF structural inspector used only by the worker.

    Only parses the document structure enough to count pages; never renders
    pages, extracts embedded content, or executes anything. Any parse failure
    (including a file that passed the API's cheap signature check but is
    actually corrupt or spoofed) is surfaced as :class:`InvalidPdfError`.
    """

    def page_count(self, stream: BinaryIO) -> int:
        try:
            reader = PdfReader(stream, strict=False)
            return len(reader.pages)
        except (PdfReadError, ValueError, KeyError, IndexError) as error:
            raise InvalidPdfError(f"not a well-formed PDF: {error}") from error
