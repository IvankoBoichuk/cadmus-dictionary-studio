"""SQLAlchemy persistence adapters for the sources module."""

from collections.abc import Iterator, Sequence
from io import BytesIO
from types import TracebackType
from typing import BinaryIO
from uuid import UUID

import pypdfium2 as pdfium
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.sources.domain import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    Contributor,
    Dictionary,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    InspectionStatus,
    PagesStatus,
    SourceFile,
)
from cadmus.sources.ports import (
    InvalidPdfError,
    RenderedPage,
    SourcesUnitOfWorkFactory,
)

_RENDER_DPI = 200
_RENDER_SCALE = _RENDER_DPI / 72

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

dictionary_abbreviations = Table(
    "dictionary_abbreviations",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("abbreviation", String(64), nullable=False),
    Column("full_form", String(512), nullable=True),
    Column("category", String(32), nullable=False),
    Column("language_code", String(2), nullable=True),
    Column("note", Text, nullable=True),
    Column("unresolved", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "updated_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    CheckConstraint(
        "category IN ('part_of_speech', 'grammar', 'usage', 'geography', "
        "'source', 'other')",
        name="dictionary_abbreviation_category",
    ),
)

dictionary_abbreviation_variants = Table(
    "dictionary_abbreviation_variants",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "abbreviation_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_abbreviations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("variant_text", String(255), nullable=False),
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
    Column("pages_status", String(16), nullable=False, server_default="pending"),
    Column("pages_error", Text, nullable=True),
    CheckConstraint(
        "inspection_status IN ('pending', 'verified', 'failed')",
        name="source_file_inspection_status",
    ),
    CheckConstraint(
        "pages_status IN ('pending', 'completed', 'failed')",
        name="source_file_pages_status",
    ),
)

dictionary_pages = Table(
    "dictionary_pages",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "source_file_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_source_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("page_index", Integer, nullable=False),
    Column("printed_page_number", Integer, nullable=True),
    Column("processed_asset_key", String(500), nullable=False, unique=True),
    Column("width", Integer, nullable=False),
    Column("height", Integer, nullable=False),
    Column("rotation", Integer, nullable=False, default=0),
    Column("checksum_sha256", String(64), nullable=False),
    Column("ocr_status", String(16), nullable=False),
    Column("layout_status", String(16), nullable=False),
    Column("validation_status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "ocr_status IN ('pending', 'processing', 'completed', 'failed')",
        name="dictionary_page_ocr_status",
    ),
    CheckConstraint(
        "layout_status IN ('pending', 'processing', 'completed', 'failed')",
        name="dictionary_page_layout_status",
    ),
    CheckConstraint(
        "validation_status IN ('pending', 'processing', 'completed', 'failed')",
        name="dictionary_page_validation_status",
    ),
    UniqueConstraint(
        "source_file_id", "page_index", name="uq_dictionary_pages_source_file_page"
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
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
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
sources_registry.map_imperatively(Abbreviation, dictionary_abbreviations)
sources_registry.map_imperatively(AbbreviationVariant, dictionary_abbreviation_variants)
sources_registry.map_imperatively(SourceFile, dictionary_source_files)
sources_registry.map_imperatively(DictionaryPage, dictionary_pages)
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

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        self._session.execute(
            delete(dictionary_pages).where(
                dictionary_pages.c.source_file_id == source_file_id
            )
        )
        for page in pages:
            self._session.add(page)

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        return list(
            self._session.scalars(
                select(SourceFile).where(
                    dictionary_source_files.c.inspection_status
                    == InspectionStatus.VERIFIED,
                    dictionary_source_files.c.pages_status != PagesStatus.COMPLETED,
                )
            )
        )

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        return self._session.scalar(
            select(DictionaryPage).where(
                dictionary_pages.c.source_file_id == source_file_id,
                dictionary_pages.c.page_index == page_index,
            )
        )

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        dictionary_ids = self._session.scalars(
            select(dictionaries.c.id)
            .where(dictionaries.c.owner_id == owner_id)
            .order_by(dictionaries.c.updated_at.desc())
        )
        return [
            dictionary
            for dictionary_id in dictionary_ids
            if (dictionary := self.get_dictionary(dictionary_id)) is not None
        ]

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        self._session.execute(
            delete(dictionaries).where(dictionaries.c.id == dictionary_id)
        )

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        abbreviation_ids = self._session.scalars(
            select(dictionary_abbreviations.c.id)
            .where(dictionary_abbreviations.c.dictionary_id == dictionary_id)
            .order_by(dictionary_abbreviations.c.abbreviation)
        )
        return [
            abbreviation
            for abbreviation_id in abbreviation_ids
            if (abbreviation := self.get_abbreviation(dictionary_id, abbreviation_id))
            is not None
        ]

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        abbreviation = self._session.get(Abbreviation, abbreviation_id)
        if abbreviation is None or abbreviation.dictionary_id != dictionary_id:
            return None
        abbreviation.variants = list(
            self._session.scalars(
                select(AbbreviationVariant)
                .where(
                    dictionary_abbreviation_variants.c.abbreviation_id
                    == abbreviation_id
                )
                .order_by(dictionary_abbreviation_variants.c.position)
            )
        )
        return abbreviation

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        conditions = [
            dictionary_abbreviations.c.dictionary_id == dictionary_id,
            dictionary_abbreviations.c.category == category,
            dictionary_abbreviations.c.language_code == language_code,
            dictionary_abbreviations.c.abbreviation == abbreviation.strip(),
        ]
        if exclude_id is not None:
            conditions.append(dictionary_abbreviations.c.id != exclude_id)
        return self._session.scalar(select(Abbreviation).where(*conditions))

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        self._session.add(abbreviation)

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        self._session.add(abbreviation)

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        self._session.execute(
            delete(dictionary_abbreviation_variants).where(
                dictionary_abbreviation_variants.c.abbreviation_id == abbreviation_id
            )
        )
        for variant in variants:
            self._session.add(variant)

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        self._session.execute(
            delete(dictionary_abbreviations).where(
                dictionary_abbreviations.c.id == abbreviation_id,
                dictionary_abbreviations.c.dictionary_id == dictionary_id,
            )
        )


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


class PypdfiumPageRenderer:
    """Bounded PDF page rasterizer used only by the worker.

    Renders each page at ``_RENDER_DPI`` and encodes it as PNG; never
    executes embedded scripts or extracts other content. Any parse failure
    is surfaced as :class:`InvalidPdfError`.
    """

    def render_pages(self, stream: BinaryIO) -> Iterator[RenderedPage]:
        try:
            document = pdfium.PdfDocument(stream.read())
        except pdfium.PdfiumError as error:
            raise InvalidPdfError(f"not a well-formed PDF: {error}") from error

        try:
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    bitmap = page.render(scale=_RENDER_SCALE)
                    image = bitmap.to_pil()
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    yield RenderedPage(
                        page_index=page_index,
                        width=image.width,
                        height=image.height,
                        content=buffer.getvalue(),
                    )
                finally:
                    page.close()
        except pdfium.PdfiumError as error:
            raise InvalidPdfError(f"not a well-formed PDF: {error}") from error
        finally:
            document.close()
