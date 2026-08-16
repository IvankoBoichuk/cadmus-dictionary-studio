"""Sources application use cases: upload, inspection, and metadata."""

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from cadmus.sources.domain import (
    ALLOWED_CONTENT_TYPE,
    ALLOWED_EXTENSION,
    ISO_639_1_CODES,
    PDF_SIGNATURE,
    Contributor,
    ContributorRole,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryEventType,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryStatus,
    DuplicateSourceError,
    InspectionStatus,
    InvalidUploadError,
    LegalStatus,
    MetadataValidationError,
    SourceFile,
    UploadTooLargeError,
    missing_required_fields,
    validate_isbn,
    validate_legal_status,
    validate_publication_year,
)
from cadmus.sources.object_storage import ObjectStorage
from cadmus.sources.ports import (
    SourceInspectionQueue,
    SourceInspectionQueueUnavailableError,
    SourcesUnitOfWorkFactory,
)

logger = logging.getLogger(__name__)

_UPLOAD_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class UploadOutcome:
    """Result of a successful upload: the new draft and its missing fields."""

    dictionary: Dictionary
    source_file: SourceFile
    missing_required_fields: list[str]


class UploadDictionaryService:
    """Validate, store, and record a newly uploaded dictionary PDF."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        object_storage: ObjectStorage,
        inspection_queue: SourceInspectionQueue,
        max_upload_size_bytes: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._object_storage = object_storage
        self._inspection_queue = inspection_queue
        self._max_upload_size_bytes = max_upload_size_bytes
        self._clock = clock

    def upload(
        self,
        owner_id: UUID,
        filename: str,
        declared_content_type: str,
        file: BinaryIO,
    ) -> UploadOutcome:
        """Validate a streamed PDF, store it, and create its dictionary draft.

        Only ever performs cheap, bounded checks (extension, declared
        content-type, the ``%PDF-`` signature, a streamed size cap, and a
        streamed SHA-256 hash) — never a structural PDF parse, which the
        worker performs asynchronously afterward.
        """
        self._validate_filename(filename)
        if declared_content_type != ALLOWED_CONTENT_TYPE:
            raise InvalidUploadError(
                "file",
                "Файл повинен мати MIME type application/pdf.",
            )

        byte_size, checksum = self._hash_and_validate_signature(file)

        existing = self._find_duplicate(owner_id, checksum)
        if existing is not None:
            raise DuplicateSourceError(existing.id, existing.title)

        storage_key = f"sources/{owner_id}/{uuid4().hex}.pdf"
        file.seek(0)
        self._object_storage.upload(storage_key, file, byte_size, ALLOWED_CONTENT_TYPE)

        now = self._clock()
        dictionary_id = uuid4()
        dictionary = Dictionary(
            id=dictionary_id,
            owner_id=owner_id,
            status=DictionaryStatus.DRAFT,
            created_at=now,
            updated_at=now,
            updated_by=owner_id,
        )
        source_file = SourceFile(
            id=uuid4(),
            dictionary_id=dictionary_id,
            original_filename=filename,
            mime_type=ALLOWED_CONTENT_TYPE,
            byte_size=byte_size,
            checksum_sha256=checksum,
            storage_key=storage_key,
            uploaded_at=now,
            uploaded_by=owner_id,
            inspection_status=InspectionStatus.PENDING,
        )

        try:
            with self._unit_of_work_factory() as unit_of_work:
                duplicate = unit_of_work.sources.find_duplicate_source(
                    owner_id, checksum
                )
                if duplicate is not None:
                    raise DuplicateSourceError(duplicate.id, duplicate.title)
                unit_of_work.sources.add_dictionary(dictionary)
                unit_of_work.sources.add_source_file(source_file)
                unit_of_work.sources.add_event(
                    DictionaryEvent(
                        id=uuid4(),
                        dictionary_id=dictionary_id,
                        event_type=DictionaryEventType.CREATED,
                        actor_user_id=owner_id,
                        occurred_at=now,
                    )
                )
                unit_of_work.sources.add_event(
                    DictionaryEvent(
                        id=uuid4(),
                        dictionary_id=dictionary_id,
                        event_type=DictionaryEventType.SOURCE_UPLOADED,
                        actor_user_id=owner_id,
                        occurred_at=now,
                    )
                )
                unit_of_work.commit()
        except Exception:
            self._object_storage.delete(storage_key)
            raise

        try:
            self._inspection_queue.enqueue_inspection(source_file.id)
        except SourceInspectionQueueUnavailableError:
            logger.warning(
                "source inspection queue unavailable; leaving inspection pending",
            )

        return UploadOutcome(
            dictionary=dictionary,
            source_file=source_file,
            missing_required_fields=missing_required_fields(dictionary),
        )

    def _find_duplicate(self, owner_id: UUID, checksum: str) -> Dictionary | None:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.sources.find_duplicate_source(owner_id, checksum)

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if not filename.lower().endswith(ALLOWED_EXTENSION):
            raise InvalidUploadError("file", "Файл повинен мати розширення .pdf.")

    def _hash_and_validate_signature(self, file: BinaryIO) -> tuple[int, str]:
        file.seek(0)
        hasher = hashlib.sha256()
        byte_size = 0
        signature_checked = False
        while True:
            chunk = file.read(_UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            byte_size += len(chunk)
            if byte_size > self._max_upload_size_bytes:
                raise UploadTooLargeError(self._max_upload_size_bytes)
            if not signature_checked:
                if not chunk.startswith(PDF_SIGNATURE):
                    raise InvalidUploadError(
                        "file",
                        "Файл не є коректним PDF (невірна сигнатура файлу).",
                    )
                signature_checked = True
            hasher.update(chunk)
        if byte_size == 0 or not signature_checked:
            raise InvalidUploadError("file", "Порожній файл неможливо завантажити.")
        return byte_size, hasher.hexdigest()


class CompleteSourceInspectionService:
    """Record the worker's asynchronous PDF structural-inspection result."""

    def __init__(self, unit_of_work_factory: SourcesUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def complete(
        self,
        source_file_id: UUID,
        *,
        page_count: int | None = None,
        error: str | None = None,
    ) -> None:
        """Apply an idempotent verified/failed transition to a source file."""
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file_by_id(source_file_id)
            if source_file is None:
                return
            if error is not None:
                source_file.mark_failed(error)
            elif page_count is not None:
                source_file.mark_verified(page_count)
            else:
                raise ValueError("either page_count or error must be provided")
            unit_of_work.sources.update_source_file(source_file)
            unit_of_work.commit()


class RecordPageSplitService:
    """Record the worker's asynchronous PDF page-splitting result."""

    def __init__(self, unit_of_work_factory: SourcesUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def record_success(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        """Persist the rendered pages and mark the split completed, atomically."""
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file_by_id(source_file_id)
            if source_file is None:
                return
            unit_of_work.sources.replace_pages(source_file_id, pages)
            source_file.mark_pages_completed()
            unit_of_work.sources.update_source_file(source_file)
            unit_of_work.commit()

    def record_failure(self, source_file_id: UUID, error: str) -> None:
        """Record a failed page split without discarding a prior success."""
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file_by_id(source_file_id)
            if source_file is None:
                return
            source_file.mark_pages_failed(error)
            unit_of_work.sources.update_source_file(source_file)
            unit_of_work.commit()


@dataclass(frozen=True)
class ContributorInput:
    """One ordered contributor entry as submitted by the client."""

    name: str
    role: ContributorRole


@dataclass(frozen=True)
class MetadataInput:
    """Bounded, already-type-checked BH-27 metadata submission."""

    title: str | None
    description: str | None
    dictionary_type: str | None
    publisher: str | None
    publication_year: int | None
    edition: str | None
    isbn: str | None
    digital_source: str | None
    legal_status: LegalStatus | None
    license_type: str | None
    permission_reference: str | None
    rights_note: str | None
    contributors: tuple[ContributorInput, ...]
    language_codes: tuple[str, ...]


@dataclass(frozen=True)
class MetadataSaveOutcome:
    """Result of a metadata save: the updated draft and its missing fields."""

    dictionary: Dictionary
    missing_required_fields: list[str]


_METADATA_FIELDS = (
    "title",
    "description",
    "dictionary_type",
    "publisher",
    "publication_year",
    "edition",
    "isbn",
    "digital_source",
    "legal_status",
    "license_type",
    "permission_reference",
    "rights_note",
)


class SaveDictionaryMetadataService:
    """Validate and persist BH-27 bibliographic, language, and legal metadata."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    def save(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        data: MetadataInput,
    ) -> MetadataSaveOutcome:
        """Save a (possibly incomplete) metadata draft; never blocks on gaps."""
        normalized_isbn, errors = self._validate(data)
        if errors:
            raise MetadataValidationError(errors)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            if dictionary is None or dictionary.owner_id != actor_id:
                raise DictionaryAccessError(dictionary_id)

            changed_fields = self._changed_fields(dictionary, data, normalized_isbn)

            dictionary.title = data.title
            dictionary.description = data.description
            dictionary.dictionary_type = data.dictionary_type
            dictionary.publisher = data.publisher
            dictionary.publication_year = data.publication_year
            dictionary.edition = data.edition
            dictionary.isbn = normalized_isbn
            dictionary.digital_source = data.digital_source
            dictionary.legal_status = data.legal_status
            dictionary.license_type = data.license_type
            dictionary.permission_reference = data.permission_reference
            dictionary.rights_note = data.rights_note
            dictionary.updated_at = now
            dictionary.updated_by = actor_id

            contributors = [
                Contributor(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    name=contributor.name,
                    role=contributor.role,
                    position=position,
                )
                for position, contributor in enumerate(data.contributors)
            ]
            languages = [
                DictionaryLanguage(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    language_code=code,
                    position=position,
                )
                for position, code in enumerate(data.language_codes)
            ]

            unit_of_work.sources.update_dictionary(dictionary)
            unit_of_work.sources.replace_contributors(dictionary_id, contributors)
            unit_of_work.sources.replace_languages(dictionary_id, languages)
            if changed_fields:
                unit_of_work.sources.add_event(
                    DictionaryEvent(
                        id=uuid4(),
                        dictionary_id=dictionary_id,
                        event_type=DictionaryEventType.METADATA_UPDATED,
                        actor_user_id=actor_id,
                        occurred_at=now,
                        changed_fields=tuple(changed_fields),
                    )
                )
            unit_of_work.commit()

        dictionary.contributors = contributors
        dictionary.languages = languages
        return MetadataSaveOutcome(
            dictionary=dictionary,
            missing_required_fields=missing_required_fields(dictionary),
        )

    @staticmethod
    def _changed_fields(
        dictionary: Dictionary, data: MetadataInput, normalized_isbn: str | None
    ) -> list[str]:
        changed = [
            field
            for field in _METADATA_FIELDS
            if getattr(dictionary, field)
            != (normalized_isbn if field == "isbn" else getattr(data, field))
        ]
        existing_contributors = [
            (contributor.name, contributor.role)
            for contributor in dictionary.contributors
        ]
        new_contributors = [
            (contributor.name, contributor.role) for contributor in data.contributors
        ]
        if existing_contributors != new_contributors:
            changed.append("contributors")
        existing_languages = [
            language.language_code for language in dictionary.languages
        ]
        if existing_languages != list(data.language_codes):
            changed.append("languages")
        return changed

    def _validate(self, data: MetadataInput) -> tuple[str | None, dict[str, str]]:
        errors: dict[str, str] = {}

        if data.title is not None and len(data.title) > 512:
            errors["title"] = "Назва занадто довга (максимум 512 символів)."

        for code in data.language_codes:
            if code not in ISO_639_1_CODES:
                errors["language_codes"] = f"Невідомий код мови: {code}."
                break

        if data.publication_year is not None:
            year_error = validate_publication_year(
                data.publication_year, current_year=self._clock().year
            )
            if year_error is not None:
                errors["publication_year"] = year_error

        normalized_isbn: str | None = None
        if data.isbn:
            normalized_isbn, isbn_error = validate_isbn(data.isbn)
            if isbn_error is not None:
                errors["isbn"] = isbn_error

        if data.legal_status is not None:
            errors.update(
                validate_legal_status(
                    data.legal_status, data.license_type, data.permission_reference
                )
            )

        return normalized_isbn, errors


class GetDictionaryService:
    """Read a dictionary draft, enforcing owner-only visibility."""

    def __init__(self, unit_of_work_factory: SourcesUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def get(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            if dictionary is None or dictionary.owner_id != actor_id:
                raise DictionaryAccessError(dictionary_id)
            return dictionary

    def get_source_file(self, dictionary_id: UUID, actor_id: UUID) -> SourceFile:
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file(dictionary.id)
            if source_file is None:
                raise DictionaryAccessError(dictionary_id)
            return source_file
