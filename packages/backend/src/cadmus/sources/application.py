"""Sources application use cases: upload, inspection, and metadata."""

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from cadmus.access import AccessDeniedError, AuthorizationService, Permission
from cadmus.geography.ports import GeographyUnitOfWorkFactory
from cadmus.sources.domain import (
    ALLOWED_CONTENT_TYPE,
    ALLOWED_EXTENSION,
    ISO_639_1_CODES,
    PDF_SIGNATURE,
    Abbreviation,
    AbbreviationAccessError,
    AbbreviationCategory,
    AbbreviationValidationError,
    AbbreviationVariant,
    Contributor,
    ContributorRole,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryEventType,
    DictionaryLanguage,
    DictionaryNotReadyError,
    DictionaryPage,
    DictionaryPageRange,
    DictionarySettlementMapping,
    DictionaryStatus,
    DuplicateAbbreviationError,
    DuplicateSettlementMappingError,
    DuplicateSourceError,
    InspectionStatus,
    InvalidUploadError,
    LegalStatus,
    MetadataValidationError,
    PageRangeInput,
    PageRangesUnavailableError,
    PageRangeValidationError,
    ProcessingSignals,
    SettlementMappingAccessError,
    SettlementMappingStatus,
    SettlementMappingValidationError,
    SourceFile,
    UploadTooLargeError,
    apply_status_after_edit,
    expand_page_ranges,
    missing_required_fields,
    next_processing_status,
    normalize_page_ranges,
    readiness_blockers,
    settlement_mapping_duplicate_key,
    validate_abbreviation_fields,
    validate_isbn,
    validate_legal_status,
    validate_page_ranges,
    validate_publication_year,
    validate_settlement_mapping_fields,
)
from cadmus.sources.object_storage import ObjectStorage
from cadmus.sources.ports import (
    SourceInspectionQueue,
    SourceInspectionQueueUnavailableError,
    SourcesUnitOfWorkFactory,
)

logger = logging.getLogger(__name__)

_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _authorize(
    authorization: AuthorizationService,
    dictionary: Dictionary | None,
    dictionary_id: UUID,
    actor_id: UUID,
    permission: Permission,
) -> Dictionary:
    """Require ``permission`` on ``dictionary_id``, hiding both absence and denial.

    A missing dictionary and a dictionary the actor lacks ``permission`` on
    both raise the same ``DictionaryAccessError`` (BH-170 AC: "недоступний
    проєкт не розкриває метадані").
    """
    if dictionary is None:
        raise DictionaryAccessError(dictionary_id)
    try:
        authorization.require(dictionary_id, dictionary.owner_id, actor_id, permission)
    except AccessDeniedError as error:
        raise DictionaryAccessError(dictionary_id) from error
    return dictionary


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
    article_description: str | None
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
    "article_description",
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
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

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
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            changed_fields = self._changed_fields(dictionary, data, normalized_isbn)

            dictionary.title = data.title
            dictionary.description = data.description
            dictionary.article_description = data.article_description
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

            previous_status = DictionaryStatus(dictionary.status)
            source_file = unit_of_work.sources.get_source_file(dictionary_id)
            page_ranges = unit_of_work.sources.list_page_ranges(dictionary_id)
            reverted = apply_status_after_edit(
                dictionary, readiness_blockers(dictionary, source_file, page_ranges)
            )
            if reverted:
                unit_of_work.sources.add_event(
                    DictionaryEvent(
                        id=uuid4(),
                        dictionary_id=dictionary_id,
                        event_type=DictionaryEventType.STATUS_CHANGED,
                        actor_user_id=actor_id,
                        occurred_at=now,
                        previous_status=previous_status,
                        new_status=dictionary.status,
                        reason="metadata_no_longer_ready",
                    )
                )

            unit_of_work.sources.update_dictionary(dictionary)
            unit_of_work.sources.replace_contributors(dictionary_id, contributors)
            unit_of_work.sources.replace_languages(dictionary_id, languages)
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


@dataclass(frozen=True)
class DictionaryListEntry:
    """One dictionary paired with its (possibly absent) source file."""

    dictionary: Dictionary
    source_file: SourceFile | None
    page_ranges: list[DictionaryPageRange]


class GetDictionaryService:
    """Read a dictionary draft, enforcing owner-only visibility."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorization = authorization or AuthorizationService()

    def get(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        *,
        required_permission: Permission = Permission.VIEW,
    ) -> Dictionary:
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            return _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                required_permission,
            )

    def get_source_file(self, dictionary_id: UUID, actor_id: UUID) -> SourceFile:
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file(dictionary.id)
            if source_file is None:
                raise DictionaryAccessError(dictionary_id)
            return source_file

    def get_page_ranges(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[DictionaryPageRange]:
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.sources.list_page_ranges(dictionary.id)

    def list_for_owner(self, owner_id: UUID) -> list[DictionaryListEntry]:
        """List every dictionary owned by ``owner_id``, newest-updated first."""
        with self._unit_of_work_factory() as unit_of_work:
            dictionaries = unit_of_work.sources.list_dictionaries_for_owner(owner_id)
            return [
                DictionaryListEntry(
                    dictionary=dictionary,
                    source_file=unit_of_work.sources.get_source_file(dictionary.id),
                    page_ranges=unit_of_work.sources.list_page_ranges(dictionary.id),
                )
                for dictionary in dictionaries
            ]

    def list_for_actor(self, actor_id: UUID) -> list[DictionaryListEntry]:
        """BH-170: dictionaries ``actor_id`` owns plus ones they're a member of."""
        entries = self.list_for_owner(actor_id)
        member_dictionary_ids = self._authorization.list_member_dictionary_ids(actor_id)
        if not member_dictionary_ids:
            return entries
        with self._unit_of_work_factory() as unit_of_work:
            for dictionary_id in member_dictionary_ids:
                dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
                if dictionary is None:
                    continue
                entries.append(
                    DictionaryListEntry(
                        dictionary=dictionary,
                        source_file=unit_of_work.sources.get_source_file(dictionary.id),
                        page_ranges=unit_of_work.sources.list_page_ranges(
                            dictionary.id
                        ),
                    )
                )
        entries.sort(key=lambda entry: entry.dictionary.updated_at, reverse=True)
        return entries

    def get_first_page(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> DictionaryPage | None:
        """Return the first rendered page of a dictionary's source, if any."""
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file(dictionary.id)
            if source_file is None:
                return None
            return unit_of_work.sources.get_page(source_file.id, page_index=0)

    def count_viewable_pages(self, dictionary_id: UUID, actor_id: UUID) -> int:
        """BH-53 AC2/AC4: total pages within the dictionary's saved ranges."""
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            ranges = unit_of_work.sources.list_page_ranges(dictionary.id)
        return len(expand_page_ranges(ranges))

    def get_viewable_page(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        ordinal: int,
        *,
        required_permission: Permission = Permission.VIEW,
    ) -> DictionaryPage | None:
        """BH-53: the ``ordinal``-th (1-based) page within the saved ranges.

        ``ordinal`` addresses position within the configured page ranges,
        not the PDF's raw physical page index -- this is what keeps the
        viewer scoped to AC4 ("лише сторінки з заданого діапазону") and
        makes an out-of-range or unconfigured request simply miss rather
        than leak pages outside the dictionary's declared scope.
        """
        dictionary = self.get(
            dictionary_id, actor_id, required_permission=required_permission
        )
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file(dictionary.id)
            if source_file is None:
                return None
            page_numbers = expand_page_ranges(
                unit_of_work.sources.list_page_ranges(dictionary.id)
            )
            if ordinal < 1 or ordinal > len(page_numbers):
                return None
            physical_page_number = page_numbers[ordinal - 1]
            return unit_of_work.sources.get_page(
                source_file.id, page_index=physical_page_number - 1
            )

    def get_page_by_id(
        self, dictionary_id: UUID, actor_id: UUID, page_id: UUID
    ) -> DictionaryPage | None:
        """BH-56: resolve a page already known by ID, scoped to the caller.

        Used by lexeme edit validation, which already has the target
        lexeme's ``page_id`` and only needs that page's dimensions -- not
        another viewer-ordinal lookup.
        """
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file(dictionary.id)
            if source_file is None:
                return None
            page = unit_of_work.sources.get_page_by_id(page_id)
            if page is None or page.source_file_id != source_file.id:
                return None
            return page

    def list_viewable_pages(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[DictionaryPage]:
        """BH-57: every page within the saved ranges, in viewer order.

        Two queries total (``list_page_ranges`` + one bulk ``list_pages``)
        regardless of page count, so callers computing per-page scan
        progress never do it with an N+1 page lookup.
        """
        dictionary = self.get(dictionary_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            source_file = unit_of_work.sources.get_source_file(dictionary.id)
            if source_file is None:
                return []
            page_numbers = expand_page_ranges(
                unit_of_work.sources.list_page_ranges(dictionary.id)
            )
            pages_by_index = {
                page.page_index: page
                for page in unit_of_work.sources.list_pages(source_file.id)
            }
        return [
            pages_by_index[number - 1]
            for number in page_numbers
            if (number - 1) in pages_by_index
        ]


class DeleteDictionaryService:
    """Delete a dictionary draft and its underlying stored objects."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        object_storage: ObjectStorage,
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._object_storage = object_storage
        self._authorization = authorization or AuthorizationService()

    def delete(self, dictionary_id: UUID, actor_id: UUID) -> None:
        """Remove the dictionary row (cascading to its children), then storage.

        The database delete is the authoritative "is it gone" answer for the
        caller and commits first; object storage cleanup afterward is
        best-effort, matching this codebase's existing posture toward
        coordinating (not two-phase-committing) Postgres and MinIO. Requires
        ``MANAGE_MEMBERS`` -- only ``Role.OWNER`` has it -- since deleting the
        whole project is a stronger action than ordinary editing.
        """
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.MANAGE_MEMBERS,
            )
            source_file = unit_of_work.sources.get_source_file(dictionary_id)
            unit_of_work.sources.delete_dictionary(dictionary_id)
            unit_of_work.commit()

        if source_file is None:
            return
        try:
            self._object_storage.delete(source_file.storage_key)
            self._object_storage.delete_prefix(f"sources/{dictionary_id}/pages/")
        except Exception:
            logger.warning(
                "failed to clean up object storage after dictionary delete",
                exc_info=True,
            )


class DictionaryReadinessService:
    """BH-31: confirm a draft's readiness and mark it ``configured`` (AC5, AC6)."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def confirm_configured(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        """Mark ``dictionary_id`` ``configured`` once every check passes.

        Raises ``DictionaryNotReadyError`` (carrying the structured blocker
        list) and leaves the draft untouched when any check fails (AC6).
        """
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            source_file = unit_of_work.sources.get_source_file(dictionary_id)
            page_ranges = unit_of_work.sources.list_page_ranges(dictionary_id)
            blockers = readiness_blockers(dictionary, source_file, page_ranges)
            if blockers:
                raise DictionaryNotReadyError(blockers)

            previous_status = DictionaryStatus(dictionary.status)
            dictionary.status = DictionaryStatus.CONFIGURED
            dictionary.updated_at = now
            dictionary.updated_by = actor_id
            unit_of_work.sources.update_dictionary(dictionary)
            if previous_status != DictionaryStatus.CONFIGURED:
                unit_of_work.sources.add_event(
                    DictionaryEvent(
                        id=uuid4(),
                        dictionary_id=dictionary_id,
                        event_type=DictionaryEventType.STATUS_CHANGED,
                        actor_user_id=actor_id,
                        occurred_at=now,
                        previous_status=previous_status,
                        new_status=DictionaryStatus.CONFIGURED,
                    )
                )
            unit_of_work.commit()
        return dictionary


class MarkDictionaryScannedService:
    """BH-58: perform the already-authorized ``configured`` -> ``scanned`` move.

    This service only performs the mutation and its audit event -- the
    "does the dictionary have at least one lexeme" precondition is a
    ``lexicography`` concern (cross-module) and is checked by the caller
    (``lexicography.FinishScanningService``) before this runs. Idempotent:
    calling this on an already-``scanned`` dictionary is a no-op, matching
    BH-58's "повторний виклик" requirement.
    """

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def mark_scanned(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            if dictionary.status == DictionaryStatus.SCANNED:
                return dictionary

            previous_status = DictionaryStatus(dictionary.status)
            dictionary.status = DictionaryStatus.SCANNED
            dictionary.updated_at = now
            dictionary.updated_by = actor_id
            unit_of_work.sources.update_dictionary(dictionary)
            unit_of_work.sources.add_event(
                DictionaryEvent(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    event_type=DictionaryEventType.STATUS_CHANGED,
                    actor_user_id=actor_id,
                    occurred_at=now,
                    previous_status=previous_status,
                    new_status=DictionaryStatus.SCANNED,
                )
            )
            unit_of_work.commit()
        return dictionary


class AdvanceDictionaryProcessingStatusService:
    """Keep a dictionary's status in step with lexeme/entry completion.

    Owns the ``scanned`` <-> ``in_progress`` <-> ``processed`` moves and their
    audit events; the decision itself lives in
    ``sources.domain.next_processing_status``. Never leaves that band, so it
    cannot undo ``configured`` or ``published``. Idempotent when the target
    already matches. The caller supplies the (cross-module) lexicography
    signals and must already be authorized to edit.
    """

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def advance(
        self, dictionary_id: UUID, actor_id: UUID, signals: ProcessingSignals
    ) -> Dictionary:
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            previous_status = DictionaryStatus(dictionary.status)
            target = next_processing_status(previous_status, signals)
            if target == previous_status:
                return dictionary

            dictionary.status = target
            dictionary.updated_at = now
            dictionary.updated_by = actor_id
            unit_of_work.sources.update_dictionary(dictionary)
            unit_of_work.sources.add_event(
                DictionaryEvent(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    event_type=DictionaryEventType.STATUS_CHANGED,
                    actor_user_id=actor_id,
                    occurred_at=now,
                    previous_status=previous_status,
                    new_status=target,
                )
            )
            unit_of_work.commit()
        return dictionary


class DictionaryNotProcessedError(Exception):
    """Raised when publishing a dictionary that is not yet ``processed``."""

    def __init__(self, dictionary_id: UUID) -> None:
        super().__init__(f"dictionary {dictionary_id} is not fully processed")
        self.dictionary_id = dictionary_id


class PublishDictionaryService:
    """Release a fully processed dictionary (``processed`` -> ``published``).

    An explicit editor action -- the auto-sync never publishes. Only a
    ``processed`` dictionary can be published; calling this on an already
    ``published`` dictionary is a no-op.
    """

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def publish(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            if dictionary.status == DictionaryStatus.PUBLISHED:
                return dictionary
            if dictionary.status != DictionaryStatus.PROCESSED:
                raise DictionaryNotProcessedError(dictionary_id)

            previous_status = DictionaryStatus(dictionary.status)
            dictionary.status = DictionaryStatus.PUBLISHED
            dictionary.updated_at = now
            dictionary.updated_by = actor_id
            unit_of_work.sources.update_dictionary(dictionary)
            unit_of_work.sources.add_event(
                DictionaryEvent(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    event_type=DictionaryEventType.STATUS_CHANGED,
                    actor_user_id=actor_id,
                    occurred_at=now,
                    previous_status=previous_status,
                    new_status=DictionaryStatus.PUBLISHED,
                )
            )
            unit_of_work.commit()
        return dictionary


@dataclass(frozen=True)
class PageRangeSaveOutcome:
    """Result of a BH-28 page-range save: the stored ranges and merge flag."""

    dictionary_id: UUID
    ranges: list[DictionaryPageRange]
    merged: bool


class SavePageRangesService:
    """Validate, normalize, and persist BH-28 page ranges for one dictionary."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def save(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        inputs: Sequence[PageRangeInput],
    ) -> PageRangeSaveOutcome:
        """Replace the dictionary's page ranges with a validated, merged set.

        Requires a source whose page count is already known (AC1); ranges
        cannot be validated against PDF bounds before that. Mirrors
        ``SaveDictionaryMetadataService``: clearing or narrowing ranges on a
        ``configured`` dictionary until it fails readiness reverts it to
        ``draft`` (BH-31 AC7) rather than being blocked.
        """
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            dictionary = _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            source_file = unit_of_work.sources.get_source_file(dictionary_id)
            if source_file is None or source_file.page_count is None:
                raise PageRangesUnavailableError(
                    "the PDF's page count is not known yet"
                )

            errors = validate_page_ranges(inputs, page_count=source_file.page_count)
            if errors:
                raise PageRangeValidationError(errors)

            merged, changed = normalize_page_ranges(inputs)
            ranges = [
                DictionaryPageRange(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    start_page=page_range.start_page,
                    end_page=page_range.end_page,
                    position=position,
                )
                for position, page_range in enumerate(merged)
            ]
            unit_of_work.sources.replace_page_ranges(dictionary_id, ranges)

            previous_status = DictionaryStatus(dictionary.status)
            reverted = apply_status_after_edit(
                dictionary, readiness_blockers(dictionary, source_file, ranges)
            )
            if reverted:
                dictionary.updated_at = now
                dictionary.updated_by = actor_id
                unit_of_work.sources.update_dictionary(dictionary)
                unit_of_work.sources.add_event(
                    DictionaryEvent(
                        id=uuid4(),
                        dictionary_id=dictionary_id,
                        event_type=DictionaryEventType.STATUS_CHANGED,
                        actor_user_id=actor_id,
                        occurred_at=now,
                        previous_status=previous_status,
                        new_status=dictionary.status,
                        reason="page_ranges_no_longer_ready",
                    )
                )

            unit_of_work.commit()
        return PageRangeSaveOutcome(
            dictionary_id=dictionary_id, ranges=ranges, merged=changed
        )


@dataclass(frozen=True)
class AbbreviationInput:
    """One BH-29 abbreviation submission, already type-checked at the boundary."""

    abbreviation: str
    category: AbbreviationCategory
    full_form: str | None
    language_code: str | None
    note: str | None
    unresolved: bool
    variants: tuple[str, ...]


def _build_abbreviation_variants(
    abbreviation_id: UUID, variant_texts: Sequence[str]
) -> list[AbbreviationVariant]:
    return [
        AbbreviationVariant(
            id=uuid4(),
            abbreviation_id=abbreviation_id,
            variant_text=text.strip(),
            position=position,
        )
        for position, text in enumerate(variant_texts)
    ]


class AbbreviationCrudService:
    """Create, read, update, and delete BH-29 dictionary abbreviations.

    Covers AC1-AC4 and AC7.
    """

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def list_for_dictionary(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[Abbreviation]:
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.VIEW,
            )
            return unit_of_work.sources.list_abbreviations(dictionary_id)

    def create(
        self, dictionary_id: UUID, actor_id: UUID, data: AbbreviationInput
    ) -> Abbreviation:
        errors = self._validate(data)
        if errors:
            raise AbbreviationValidationError(errors)

        now = self._clock()
        abbreviation_id = uuid4()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            duplicate = unit_of_work.sources.find_abbreviation_duplicate(
                dictionary_id, data.category, data.language_code, data.abbreviation
            )
            if duplicate is not None:
                raise DuplicateAbbreviationError(duplicate.id, duplicate.abbreviation)

            abbreviation = Abbreviation(
                id=abbreviation_id,
                dictionary_id=dictionary_id,
                abbreviation=data.abbreviation.strip(),
                category=data.category,
                unresolved=data.unresolved,
                created_at=now,
                updated_at=now,
                created_by=actor_id,
                updated_by=actor_id,
                full_form=(data.full_form or "").strip() or None,
                language_code=data.language_code,
                note=(data.note or "").strip() or None,
            )
            variants = _build_abbreviation_variants(abbreviation_id, data.variants)
            unit_of_work.sources.add_abbreviation(abbreviation)
            unit_of_work.sources.replace_abbreviation_variants(
                abbreviation_id, variants
            )
            unit_of_work.commit()

        abbreviation.variants = variants
        return abbreviation

    def update(
        self,
        dictionary_id: UUID,
        abbreviation_id: UUID,
        actor_id: UUID,
        data: AbbreviationInput,
    ) -> Abbreviation:
        errors = self._validate(data)
        if errors:
            raise AbbreviationValidationError(errors)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )
            existing = unit_of_work.sources.get_abbreviation(
                dictionary_id, abbreviation_id
            )
            if existing is None:
                raise AbbreviationAccessError(abbreviation_id)

            duplicate = unit_of_work.sources.find_abbreviation_duplicate(
                dictionary_id,
                data.category,
                data.language_code,
                data.abbreviation,
                exclude_id=abbreviation_id,
            )
            if duplicate is not None:
                raise DuplicateAbbreviationError(duplicate.id, duplicate.abbreviation)

            existing.abbreviation = data.abbreviation.strip()
            existing.category = data.category
            existing.unresolved = data.unresolved
            existing.full_form = (data.full_form or "").strip() or None
            existing.language_code = data.language_code
            existing.note = (data.note or "").strip() or None
            existing.updated_at = now
            existing.updated_by = actor_id

            variants = _build_abbreviation_variants(abbreviation_id, data.variants)
            unit_of_work.sources.update_abbreviation(existing)
            unit_of_work.sources.replace_abbreviation_variants(
                abbreviation_id, variants
            )
            unit_of_work.commit()

        existing.variants = variants
        return existing

    def delete(
        self, dictionary_id: UUID, abbreviation_id: UUID, actor_id: UUID
    ) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )
            existing = unit_of_work.sources.get_abbreviation(
                dictionary_id, abbreviation_id
            )
            if existing is None:
                raise AbbreviationAccessError(abbreviation_id)
            unit_of_work.sources.delete_abbreviation(dictionary_id, abbreviation_id)
            unit_of_work.commit()

    @staticmethod
    def _validate(data: AbbreviationInput) -> dict[str, str]:
        return validate_abbreviation_fields(
            abbreviation=data.abbreviation,
            full_form=data.full_form,
            language_code=data.language_code,
            note=data.note,
            unresolved=data.unresolved,
            variants=data.variants,
        )


@dataclass(frozen=True)
class SettlementMappingInput:
    """One BH-30 settlement mapping submission, type-checked at the boundary.

    ``status`` may only be ``UNRESOLVED`` or ``SUGGESTED`` here --
    ``SettlementMappingCrudService`` rejects ``CONFIRMED`` (AC9: the only
    path that can set it is ``SettlementConfirmationService.confirm``).
    """

    source_label: str
    source_note: str | None
    modern_settlement_name: str | None
    settlement_category: str | None
    settlement_id: UUID | None
    status: SettlementMappingStatus


@dataclass(frozen=True)
class SettlementSuggestion:
    """One AC8 search result: a settlement flattened with its hierarchy."""

    settlement_id: UUID
    title: str
    category: str
    community_id: UUID
    community_name: str
    region_id: UUID
    area_id: UUID


class SettlementMappingCrudService:
    """Create, read, update, and delete BH-30 settlement mappings.

    Covers AC7, AC11, AC12, AC13. Mirrors ``AbbreviationCrudService``: every
    call re-checks ownership inside a fresh unit of work, never trusting a
    cached ``Dictionary``.
    """

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        geography_unit_of_work_factory: GeographyUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._geography_unit_of_work_factory = geography_unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def list_for_dictionary(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[DictionarySettlementMapping]:
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.VIEW,
            )
            return unit_of_work.sources.list_settlement_mappings(dictionary_id)

    def create(
        self, dictionary_id: UUID, actor_id: UUID, data: SettlementMappingInput
    ) -> DictionarySettlementMapping:
        errors = self._validate(data)
        if errors:
            raise SettlementMappingValidationError(errors)

        now = self._clock()
        mapping_id = uuid4()
        settlement_category, community_id, region_id, area_id = (
            self._resolve_settlement(data.settlement_id, data.settlement_category)
        )
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )

            duplicate = unit_of_work.sources.find_settlement_mapping_duplicate(
                dictionary_id,
                settlement_mapping_duplicate_key(data.source_label),
                settlement_id=data.settlement_id,
            )
            if duplicate is not None:
                raise DuplicateSettlementMappingError(
                    duplicate.id, duplicate.source_label
                )

            mapping = DictionarySettlementMapping(
                id=mapping_id,
                dictionary_id=dictionary_id,
                source_label=data.source_label.strip(),
                status=data.status,
                created_at=now,
                updated_at=now,
                created_by=actor_id,
                updated_by=actor_id,
                source_note=(data.source_note or "").strip() or None,
                modern_settlement_name=(data.modern_settlement_name or "").strip()
                or None,
                settlement_category=settlement_category,
                settlement_id=data.settlement_id,
                community_id=community_id,
                region_id=region_id,
                area_id=area_id,
            )
            unit_of_work.sources.add_settlement_mapping(mapping)
            unit_of_work.commit()
        return mapping

    def update(
        self,
        dictionary_id: UUID,
        mapping_id: UUID,
        actor_id: UUID,
        data: SettlementMappingInput,
    ) -> DictionarySettlementMapping:
        errors = self._validate(data)
        if errors:
            raise SettlementMappingValidationError(errors)

        now = self._clock()
        settlement_category, community_id, region_id, area_id = (
            self._resolve_settlement(data.settlement_id, data.settlement_category)
        )
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )
            existing = unit_of_work.sources.get_settlement_mapping(
                dictionary_id, mapping_id
            )
            if existing is None:
                raise SettlementMappingAccessError(mapping_id)

            duplicate = unit_of_work.sources.find_settlement_mapping_duplicate(
                dictionary_id,
                settlement_mapping_duplicate_key(data.source_label),
                settlement_id=data.settlement_id,
                exclude_id=mapping_id,
            )
            if duplicate is not None:
                raise DuplicateSettlementMappingError(
                    duplicate.id, duplicate.source_label
                )

            existing.source_label = data.source_label.strip()
            existing.status = data.status
            existing.source_note = (data.source_note or "").strip() or None
            existing.modern_settlement_name = (
                data.modern_settlement_name or ""
            ).strip() or None
            existing.settlement_category = settlement_category
            existing.settlement_id = data.settlement_id
            existing.community_id = community_id
            existing.region_id = region_id
            existing.area_id = area_id
            existing.updated_at = now
            existing.updated_by = actor_id

            unit_of_work.sources.update_settlement_mapping(existing)
            unit_of_work.commit()
        return existing

    def delete(self, dictionary_id: UUID, mapping_id: UUID, actor_id: UUID) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )
            existing = unit_of_work.sources.get_settlement_mapping(
                dictionary_id, mapping_id
            )
            if existing is None:
                raise SettlementMappingAccessError(mapping_id)
            unit_of_work.sources.delete_settlement_mapping(dictionary_id, mapping_id)
            unit_of_work.commit()

    def unconfirm(
        self, dictionary_id: UUID, mapping_id: UUID, actor_id: UUID
    ) -> DictionarySettlementMapping:
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )
            existing = unit_of_work.sources.get_settlement_mapping(
                dictionary_id, mapping_id
            )
            if existing is None:
                raise SettlementMappingAccessError(mapping_id)

            existing.status = SettlementMappingStatus.UNRESOLVED
            existing.confirmed_by = None
            existing.confirmed_at = None
            existing.updated_at = now
            existing.updated_by = actor_id

            unit_of_work.sources.update_settlement_mapping(existing)
            unit_of_work.commit()
        return existing

    def _resolve_settlement(
        self, settlement_id: UUID | None, settlement_category: str | None
    ) -> tuple[str | None, UUID | None, UUID | None, UUID | None]:
        """Best-effort hierarchy lookup for a chosen search result.

        Only fills in display fields the caller didn't already supply;
        never raises if the settlement can no longer be found (a stale
        search selection just falls back to whatever the caller sent).
        """
        if settlement_id is None:
            return settlement_category, None, None, None
        with self._geography_unit_of_work_factory() as geography_unit_of_work:
            settlement = geography_unit_of_work.geography.get_settlement(settlement_id)
            if settlement is None:
                return settlement_category, None, None, None
            community = geography_unit_of_work.geography.get_community(
                settlement.community_id
            )
            if community is None:
                return settlement_category or settlement.category, None, None, None
            return (
                settlement_category or settlement.category,
                community.id,
                community.region_id,
                community.area_id,
            )

    @staticmethod
    def _validate(data: SettlementMappingInput) -> dict[str, str]:
        errors = validate_settlement_mapping_fields(
            source_label=data.source_label,
            source_note=data.source_note,
            modern_settlement_name=data.modern_settlement_name,
        )
        if data.status is SettlementMappingStatus.CONFIRMED:
            errors["status"] = (
                'Статус "підтверджено" встановлюється лише через '
                "підтвердження відповідності, не напряму."
            )
        return errors


class SettlementSearchService:
    """AC8/AC9 -- search the local geography cache for a modern settlement.

    Reads only, never writes a mapping, never calls the external API. The
    constructor takes only a ``GeographyUnitOfWorkFactory`` so it cannot
    touch ``SourcesRepository`` even by mistake.
    """

    def __init__(
        self, geography_unit_of_work_factory: GeographyUnitOfWorkFactory
    ) -> None:
        self._geography_unit_of_work_factory = geography_unit_of_work_factory

    def search(
        self,
        *,
        query: str | None,
        area_id: UUID | None,
        region_id: UUID | None,
        community_id: UUID | None,
        category: str | None,
    ) -> list[SettlementSuggestion]:
        with self._geography_unit_of_work_factory() as unit_of_work:
            results = unit_of_work.geography.search_settlements(
                query=query,
                area_id=area_id,
                region_id=region_id,
                community_id=community_id,
                category=category,
            )
            return [
                SettlementSuggestion(
                    settlement_id=settlement.id,
                    title=settlement.title,
                    category=settlement.category,
                    community_id=community.id,
                    community_name=community.name,
                    region_id=community.region_id,
                    area_id=community.area_id,
                )
                for settlement, community in results
            ]


class SettlementConfirmationService:
    """The only code path allowed to set ``status=CONFIRMED`` (AC9).

    Re-reads the current settlement/community/region/area hierarchy from
    ``geography`` and snapshots it onto the mapping (AC10), rather than
    trusting whatever was cached on the mapping at ``create``/``update``
    time.
    """

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        geography_unit_of_work_factory: GeographyUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        authorization: AuthorizationService | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._geography_unit_of_work_factory = geography_unit_of_work_factory
        self._clock = clock
        self._authorization = authorization or AuthorizationService()

    def confirm(
        self, dictionary_id: UUID, mapping_id: UUID, actor_id: UUID
    ) -> DictionarySettlementMapping:
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            _authorize(
                self._authorization,
                dictionary,
                dictionary_id,
                actor_id,
                Permission.EDIT,
            )
            mapping = unit_of_work.sources.get_settlement_mapping(
                dictionary_id, mapping_id
            )
            if mapping is None:
                raise SettlementMappingAccessError(mapping_id)
            if mapping.settlement_id is None:
                raise SettlementMappingValidationError(
                    {
                        "settlement_id": (
                            "Спочатку оберіть сучасний населений пункт через пошук."
                        )
                    }
                )

            with self._geography_unit_of_work_factory() as geography_unit_of_work:
                settlement = geography_unit_of_work.geography.get_settlement(
                    mapping.settlement_id
                )
                community = (
                    geography_unit_of_work.geography.get_community(
                        settlement.community_id
                    )
                    if settlement is not None
                    else None
                )
                region = (
                    geography_unit_of_work.geography.get_region(community.region_id)
                    if community is not None
                    else None
                )
                area = (
                    geography_unit_of_work.geography.get_area(community.area_id)
                    if community is not None
                    else None
                )
            if (
                settlement is None
                or community is None
                or region is None
                or area is None
            ):
                raise SettlementMappingValidationError(
                    {
                        "settlement_id": (
                            "Обраний населений пункт більше не входить до "
                            "довідника. Оберіть інший."
                        )
                    }
                )

            mapping.settlement_category = settlement.category
            mapping.community_id = community.id
            mapping.region_id = region.id
            mapping.area_id = area.id
            mapping.area_name = area.name
            mapping.region_name = region.name
            mapping.community_name = community.name
            mapping.external_community_id = community.external_id
            mapping.katottg = community.katottg
            mapping.koatuu = community.koatuu
            mapping.status = SettlementMappingStatus.CONFIRMED
            mapping.confirmed_by = actor_id
            mapping.confirmed_at = now
            mapping.updated_at = now
            mapping.updated_by = actor_id

            unit_of_work.sources.update_settlement_mapping(mapping)
            unit_of_work.commit()
        return mapping
