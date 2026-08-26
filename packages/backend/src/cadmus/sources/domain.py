"""Sources domain objects and invariants for the dictionary draft aggregate."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

PDF_SIGNATURE = b"%PDF-"
ALLOWED_EXTENSION = ".pdf"
ALLOWED_CONTENT_TYPE = "application/pdf"

MIN_PUBLICATION_YEAR = 1450
"""Earliest plausible printed-dictionary year (movable-type printing press era)."""

# ISO 639-1 two-letter language codes.
ISO_639_1_CODES: frozenset[str] = frozenset(
    """
    aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch
    co cr cs cu cv cy da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga
    gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is it iu ja
    jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv
    mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om or
    os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr
    ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi
    vo wa wo xh yi yo za zh zu
    """.split()
)


class DictionaryStatus(StrEnum):
    """Dictionary lifecycle status (BH-27, BH-31, and BH-58)."""

    DRAFT = "draft"
    CONFIGURED = "configured"
    SCANNED = "scanned"


class LegalStatus(StrEnum):
    """Recorded legal status of the digitized source."""

    PUBLIC_DOMAIN = "public_domain"
    LICENSED = "licensed"
    PERMISSION_GRANTED = "permission_granted"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class ContributorRole(StrEnum):
    """Supported contributor roles."""

    AUTHOR = "author"
    COMPILER = "compiler"


class AbbreviationCategory(StrEnum):
    """BH-29 abbreviation classification used by rules and extraction."""

    PART_OF_SPEECH = "part_of_speech"
    GRAMMAR = "grammar"
    USAGE = "usage"
    GEOGRAPHY = "geography"
    SOURCE = "source"
    OTHER = "other"


class SettlementMappingStatus(StrEnum):
    """BH-30 lifecycle of one dictionary-scoped geographic label mapping."""

    UNRESOLVED = "unresolved"
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"


class InspectionStatus(StrEnum):
    """Lifecycle of the asynchronous, worker-side PDF structural inspection."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class PagesStatus(StrEnum):
    """Lifecycle of the asynchronous, worker-side page-splitting stage."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class PageProcessingStatus(StrEnum):
    """Per-page downstream processing status (OCR, layout, validation).

    Nothing transitions these yet; the columns exist now, per ADR-0006, so
    later OCR/layout Stories don't need another migration.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DictionaryEventType(StrEnum):
    """Append-only audit event kinds."""

    CREATED = "created"
    SOURCE_UPLOADED = "source_uploaded"
    METADATA_UPDATED = "metadata_updated"
    STATUS_CHANGED = "status_changed"


REQUIRED_FIELDS: tuple[str, ...] = ("title", "languages", "legal_status")


class InvalidUploadError(ValueError):
    """A field-addressable upload validation failure."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class UploadTooLargeError(ValueError):
    """Raised when the streamed upload exceeds the configured size limit."""

    def __init__(self, max_size_bytes: int) -> None:
        super().__init__(f"upload exceeds the maximum of {max_size_bytes} bytes")
        self.max_size_bytes = max_size_bytes


class DuplicateSourceError(ValueError):
    """Raised when the checksum matches a source already owned by the caller."""

    def __init__(self, dictionary_id: UUID, title: str | None) -> None:
        super().__init__("a source with this checksum already exists")
        self.dictionary_id = dictionary_id
        self.title = title


class DictionaryAccessError(LookupError):
    """Raised for a missing dictionary or one the caller does not own.

    Intentionally indistinguishable from "not found" so existence of another
    user's dictionary is never disclosed.
    """

    def __init__(self, dictionary_id: UUID) -> None:
        super().__init__(f"dictionary {dictionary_id} is not accessible")
        self.dictionary_id = dictionary_id


class MetadataValidationError(ValueError):
    """Field-addressable dictionary metadata validation errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("dictionary metadata is invalid")
        self.errors = dict(errors)


class AbbreviationValidationError(ValueError):
    """Field-addressable abbreviation validation errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("abbreviation is invalid")
        self.errors = dict(errors)


class AbbreviationAccessError(LookupError):
    """Raised for a missing abbreviation or one outside the given dictionary."""

    def __init__(self, abbreviation_id: UUID) -> None:
        super().__init__(f"abbreviation {abbreviation_id} is not accessible")
        self.abbreviation_id = abbreviation_id


class DuplicateAbbreviationError(ValueError):
    """Raised when the same abbreviation/category/language already exists."""

    def __init__(self, existing_id: UUID, abbreviation: str) -> None:
        super().__init__("an abbreviation with this key already exists")
        self.existing_id = existing_id
        self.abbreviation = abbreviation


class SettlementMappingValidationError(ValueError):
    """Field-addressable BH-30 settlement mapping validation errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("settlement mapping is invalid")
        self.errors = dict(errors)


class SettlementMappingAccessError(LookupError):
    """Raised for a missing settlement mapping or one outside the dictionary."""

    def __init__(self, mapping_id: UUID) -> None:
        super().__init__(f"settlement mapping {mapping_id} is not accessible")
        self.mapping_id = mapping_id


class DuplicateSettlementMappingError(ValueError):
    """Raised when the same (dictionary, source label) already exists."""

    def __init__(self, existing_id: UUID, source_label: str) -> None:
        super().__init__("a settlement mapping with this label already exists")
        self.existing_id = existing_id
        self.source_label = source_label


class DictionaryNotReadyError(ValueError):
    """BH-31 AC6: raised when a draft fails readiness and cannot be configured."""

    def __init__(self, blockers: "list[ReadinessBlocker]") -> None:
        super().__init__("dictionary is not ready to be marked as configured")
        self.blockers = list(blockers)


class PageRangeValidationError(ValueError):
    """Field-addressable BH-28 page-range validation errors (AC4, AC5)."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("page ranges are invalid")
        self.errors = dict(errors)


class PageRangesUnavailableError(ValueError):
    """Raised when ranges are saved before the PDF's page count is known."""


@dataclass
class Contributor:
    """An ordered author or compiler entry belonging to one dictionary."""

    id: UUID
    dictionary_id: UUID
    name: str
    role: ContributorRole
    position: int


@dataclass
class DictionaryLanguage:
    """One structured language entry belonging to one dictionary."""

    id: UUID
    dictionary_id: UUID
    language_code: str
    position: int


@dataclass
class AbbreviationVariant:
    """One alternate spelling of an abbreviation, ordered within its parent."""

    id: UUID
    abbreviation_id: UUID
    variant_text: str
    position: int


@dataclass
class Abbreviation:
    """One BH-29 dictionary-scoped abbreviation configuration entry."""

    id: UUID
    dictionary_id: UUID
    abbreviation: str
    category: AbbreviationCategory
    unresolved: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
    full_form: str | None = None
    language_code: str | None = None
    note: str | None = None
    variants: list[AbbreviationVariant] = field(default_factory=list)


@dataclass
class DictionarySettlementMapping:
    """One BH-30 dictionary-scoped geographic label mapping entry.

    ``source_label`` is the historical/original form and is never overwritten
    by the modern equivalent (AC7). ``area_name``/``region_name``/
    ``community_name``/``external_community_id``/``katottg``/``koatuu`` are a
    snapshot taken at confirmation time (AC10), independent of the live
    ``area_id``/``region_id``/``community_id``/``settlement_id`` references
    into the ``geography`` reference-data cache, so a later resync or rename
    there never mutates an already-confirmed mapping.
    """

    id: UUID
    dictionary_id: UUID
    source_label: str
    status: SettlementMappingStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
    source_note: str | None = None
    modern_settlement_name: str | None = None
    settlement_category: str | None = None
    area_id: UUID | None = None
    region_id: UUID | None = None
    community_id: UUID | None = None
    settlement_id: UUID | None = None
    community_geometry_id: UUID | None = None
    area_name: str | None = None
    region_name: str | None = None
    community_name: str | None = None
    external_community_id: str | None = None
    katottg: str | None = None
    koatuu: str | None = None
    confirmed_by: UUID | None = None
    confirmed_at: datetime | None = None


@dataclass
class DictionaryPageRange:
    """One BH-28 physical-page-index range of dictionary entries to process.

    ``start_page``/``end_page`` are 1-based, inclusive, and refer to the
    PDF's physical page index — never the printed page number shown on the
    page itself (see ``DictionaryPage.printed_page_number`` for that).
    """

    id: UUID
    dictionary_id: UUID
    start_page: int
    end_page: int
    position: int


@dataclass
class SourceFile:
    """Immutable technical facts about the uploaded PDF and its inspection."""

    id: UUID
    dictionary_id: UUID
    original_filename: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    storage_key: str
    uploaded_at: datetime
    uploaded_by: UUID
    inspection_status: InspectionStatus
    page_count: int | None = None
    inspection_error: str | None = None
    pages_status: PagesStatus = PagesStatus.PENDING
    pages_error: str | None = None

    def mark_verified(self, page_count: int) -> None:
        """Record a successful worker-side structural inspection, idempotently."""
        if self.inspection_status is InspectionStatus.VERIFIED:
            return
        self.inspection_status = InspectionStatus.VERIFIED
        self.page_count = page_count
        self.inspection_error = None

    def mark_failed(self, reason: str) -> None:
        """Record a failed inspection without downgrading a verified result."""
        if self.inspection_status is InspectionStatus.VERIFIED:
            return
        self.inspection_status = InspectionStatus.FAILED
        self.inspection_error = reason

    def mark_pages_completed(self) -> None:
        """Record a successful worker-side page split, idempotently."""
        self.pages_status = PagesStatus.COMPLETED
        self.pages_error = None

    def mark_pages_failed(self, reason: str) -> None:
        """Record a failed page split without downgrading a completed result."""
        if self.pages_status is PagesStatus.COMPLETED:
            return
        self.pages_status = PagesStatus.FAILED
        self.pages_error = reason


@dataclass
class DictionaryPage:
    """One rendered page of an uploaded PDF (ADR-0006).

    Deliberately omits ADR-0006's ``original_asset_key``: for a single-PDF
    upload it would always duplicate ``SourceFile.storage_key``; add it if
    an archive-of-scans upload path is introduced later.
    """

    id: UUID
    source_file_id: UUID
    page_index: int
    processed_asset_key: str
    width: int
    height: int
    checksum_sha256: str
    created_at: datetime
    rotation: int = 0
    printed_page_number: int | None = None
    ocr_status: PageProcessingStatus = PageProcessingStatus.PENDING
    layout_status: PageProcessingStatus = PageProcessingStatus.PENDING
    validation_status: PageProcessingStatus = PageProcessingStatus.PENDING


@dataclass
class DictionaryEvent:
    """One append-only provenance/audit entry for a dictionary draft.

    ``previous_status``/``new_status``/``reason`` are populated only for
    ``STATUS_CHANGED`` events (BH-31 AC10); ``reason`` distinguishes a
    system-triggered reversion (AC7) from an explicit user confirmation.
    """

    id: UUID
    dictionary_id: UUID
    event_type: DictionaryEventType
    actor_user_id: UUID
    occurred_at: datetime
    changed_fields: tuple[str, ...] = ()
    previous_status: DictionaryStatus | None = None
    new_status: DictionaryStatus | None = None
    reason: str | None = None


@dataclass
class Dictionary:
    """The dictionary draft aggregate: bibliographic, language, legal metadata."""

    id: UUID
    owner_id: UUID
    status: DictionaryStatus
    created_at: datetime
    updated_at: datetime
    updated_by: UUID
    title: str | None = None
    description: str | None = None
    article_description: str | None = None
    dictionary_type: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    edition: str | None = None
    isbn: str | None = None
    digital_source: str | None = None
    legal_status: LegalStatus | None = None
    license_type: str | None = None
    permission_reference: str | None = None
    rights_note: str | None = None
    contributors: list[Contributor] = field(default_factory=list)
    languages: list[DictionaryLanguage] = field(default_factory=list)


def missing_required_fields(dictionary: Dictionary) -> list[str]:
    """List required-for-readiness fields that are still absent.

    This never blocks a draft save (BH-27 AC4); BH-31 later decides whether
    an empty result is sufficient to move to ``configured``.
    """
    missing: list[str] = []
    if not dictionary.title or not dictionary.title.strip():
        missing.append("title")
    if not dictionary.languages:
        missing.append("languages")
    if dictionary.legal_status is None:
        missing.append("legal_status")
    return missing


_MISSING_FIELD_MESSAGES: dict[str, str] = {
    "title": "Вкажіть назву словника.",
    "languages": "Вкажіть щонайменше одну мову.",
    "legal_status": "Вкажіть правовий статус.",
}


@dataclass(frozen=True)
class ReadinessBlocker:
    """One reason a draft cannot yet become ``configured`` (BH-31 AC3, AC4)."""

    code: str
    message: str


def readiness_blockers(
    dictionary: Dictionary,
    source_file: SourceFile | None,
    page_ranges: Sequence[DictionaryPageRange] | None = None,
) -> list[ReadinessBlocker]:
    """List every reason ``dictionary`` cannot become ``configured`` (AC4).

    Combines BH-27's required metadata, BH-26's PDF availability, and
    BH-28's page ranges. ``page_ranges`` defaults to ``None`` (treated as
    "none configured") only to keep call sites that predate BH-28 valid;
    every current caller passes the dictionary's actual list.
    """
    blockers = [
        ReadinessBlocker(code=field, message=_MISSING_FIELD_MESSAGES[field])
        for field in missing_required_fields(dictionary)
    ]
    if source_file is None:
        blockers.append(
            ReadinessBlocker(
                code="source_missing", message="Завантажте файл словника (PDF)."
            )
        )
    elif source_file.inspection_status == InspectionStatus.FAILED:
        blockers.append(
            ReadinessBlocker(
                code="source_invalid",
                message="Перевірка PDF завершилася помилкою. Завантажте файл повторно.",
            )
        )
    elif source_file.inspection_status != InspectionStatus.VERIFIED:
        blockers.append(
            ReadinessBlocker(
                code="source_not_verified",
                message="Перевірка PDF ще триває. Зачекайте на її завершення.",
            )
        )
    if not page_ranges:
        blockers.append(
            ReadinessBlocker(
                code="page_ranges_missing",
                message="Вкажіть щонайменше один діапазон сторінок для обробки.",
            )
        )
    return blockers


def apply_status_after_edit(
    dictionary: Dictionary, blockers: Sequence[ReadinessBlocker]
) -> bool:
    """Revert a ``configured`` draft to ``draft`` once it fails readiness (AC7).

    Editing is never blocked (mirrors the BH-27 draft-save philosophy); a
    ``configured`` dictionary that no longer satisfies readiness is instead
    demoted automatically. Returns ``True`` iff the status changed.
    """
    if dictionary.status == DictionaryStatus.CONFIGURED and blockers:
        dictionary.status = DictionaryStatus.DRAFT
        return True
    return False


def validate_publication_year(year: int, *, current_year: int) -> str | None:
    """Return an error message for an impossible publication year, else None."""
    if year < MIN_PUBLICATION_YEAR or year > current_year + 1:
        return (
            f"Рік видання має бути в межах від {MIN_PUBLICATION_YEAR} "
            f"до {current_year + 1}."
        )
    return None


def normalize_isbn(raw: str) -> str:
    """Strip formatting characters and upper-case the checksum digit."""
    return re.sub(r"[\s-]", "", raw).upper()


def validate_isbn(raw: str) -> tuple[str, str | None]:
    """Normalize an ISBN and validate its ISBN-10 or ISBN-13 checksum."""
    normalized = normalize_isbn(raw)
    if len(normalized) == 10:
        if _isbn10_checksum_valid(normalized):
            return normalized, None
        return normalized, "Некоректна контрольна сума ISBN-10."
    if len(normalized) == 13:
        if _isbn13_checksum_valid(normalized):
            return normalized, None
        return normalized, "Некоректна контрольна сума ISBN-13."
    return normalized, "ISBN має містити 10 чи 13 символів."


def _isbn10_checksum_valid(value: str) -> bool:
    if re.fullmatch(r"\d{9}[\dX]", value) is None:
        return False
    total = sum(
        (10 - index) * (10 if char == "X" else int(char))
        for index, char in enumerate(value)
    )
    return total % 11 == 0


def _isbn13_checksum_valid(value: str) -> bool:
    if re.fullmatch(r"\d{13}", value) is None:
        return False
    total = sum(
        int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(value)
    )
    return total % 10 == 0


def validate_legal_status(
    legal_status: LegalStatus,
    license_type: str | None,
    permission_reference: str | None,
) -> dict[str, str]:
    """Validate the conditional fields required by a specific legal status."""
    errors: dict[str, str] = {}
    if legal_status is LegalStatus.LICENSED and not (
        license_type and license_type.strip()
    ):
        errors["license_type"] = "Вкажіть тип ліцензії для статусу 'licensed'."
    if legal_status is LegalStatus.PERMISSION_GRANTED and not (
        permission_reference and permission_reference.strip()
    ):
        errors["permission_reference"] = "Вкажіть ідентифікатор чи опис дозволу."
    return errors


def validate_abbreviation_fields(
    *,
    abbreviation: str,
    full_form: str | None,
    language_code: str | None,
    note: str | None,
    unresolved: bool,
    variants: Sequence[str],
) -> dict[str, str]:
    """Validate one BH-29 abbreviation entry's fields (AC1, AC2)."""
    errors: dict[str, str] = {}

    if not abbreviation or not abbreviation.strip():
        errors["abbreviation"] = "Вкажіть скорочення."
    elif len(abbreviation) > 64:
        errors["abbreviation"] = "Скорочення занадто довге (максимум 64 символи)."

    if not unresolved and not (full_form and full_form.strip()):
        errors["full_form"] = (
            "Вкажіть повну форму. Якщо вона невідома, позначте запис як "
            "нерозшифрований."
        )
    elif full_form is not None and len(full_form) > 512:
        errors["full_form"] = "Повна форма занадто довга (максимум 512 символів)."

    if language_code is not None and language_code not in ISO_639_1_CODES:
        errors["language_code"] = f"Невідомий код мови: {language_code}."

    if note is not None and len(note) > 2000:
        errors["note"] = "Примітка занадто довга (максимум 2000 символів)."

    for variant in variants:
        if not variant.strip():
            errors["variants"] = "Варіант написання не може бути порожнім."
            break
        if len(variant) > 255:
            errors["variants"] = "Варіант написання занадто довгий (максимум 255)."
            break

    return errors


def abbreviation_duplicate_key(
    category: AbbreviationCategory, language_code: str | None, abbreviation: str
) -> tuple[AbbreviationCategory, str | None, str]:
    """Normalize the fields AC4 compares to detect a duplicate entry."""
    return category, language_code, abbreviation.strip()


def validate_settlement_mapping_fields(
    *,
    source_label: str,
    source_note: str | None,
    modern_settlement_name: str | None,
) -> dict[str, str]:
    """Validate one BH-30 settlement mapping entry's fields (BH-48)."""
    errors: dict[str, str] = {}

    if not source_label or not source_label.strip():
        errors["source_label"] = "Вкажіть географічну позначку з оригіналу."
    elif len(source_label) > 512:
        errors["source_label"] = (
            "Географічна позначка занадто довга (максимум 512 символів)."
        )

    if source_note is not None and len(source_note) > 2000:
        errors["source_note"] = "Примітка занадто довга (максимум 2000 символів)."

    if modern_settlement_name is not None and len(modern_settlement_name) > 255:
        errors["modern_settlement_name"] = (
            "Назва сучасного населеного пункту занадто довга (максимум 255 символів)."
        )

    return errors


def settlement_mapping_duplicate_key(source_label: str) -> str:
    """Normalize the field used to detect a duplicate mapping (trim-only)."""
    return source_label.strip()


@dataclass(frozen=True)
class PageRangeInput:
    """One BH-28 page range as submitted by the client, pre-persistence."""

    start_page: int
    end_page: int


def validate_page_ranges(
    ranges: Sequence[PageRangeInput], *, page_count: int
) -> dict[str, str]:
    """Validate each range's PDF bounds (AC4) and start/end order (AC5).

    Errors are keyed ``ranges.<index>.<field>`` so the client can address
    the specific row and field that failed.
    """
    errors: dict[str, str] = {}
    for index, page_range in enumerate(ranges):
        start_key = f"ranges.{index}.start_page"
        end_key = f"ranges.{index}.end_page"
        if page_range.start_page < 1 or page_range.start_page > page_count:
            errors[start_key] = (
                f"Початкова сторінка має бути в межах від 1 до {page_count}."
            )
        if page_range.end_page < 1 or page_range.end_page > page_count:
            errors[end_key] = (
                f"Кінцева сторінка має бути в межах від 1 до {page_count}."
            )
        if (
            start_key not in errors
            and end_key not in errors
            and page_range.start_page > page_range.end_page
        ):
            errors[end_key] = "Кінцева сторінка має бути не меншою за початкову."
    return errors


def expand_page_ranges(ranges: Sequence[DictionaryPageRange]) -> list[int]:
    """Flatten saved page ranges into their ordered physical page numbers.

    ``ranges`` are expected pre-merged and position-ordered, which
    ``normalize_page_ranges`` already guarantees at save time, so this only
    expands and concatenates them. Used by BH-53's page viewer to scope
    navigation to "лише сторінки з заданого діапазону" (AC4) without
    exposing pages outside the configured ranges.
    """
    ordered = sorted(ranges, key=lambda r: r.position)
    numbers: list[int] = []
    for page_range in ordered:
        numbers.extend(range(page_range.start_page, page_range.end_page + 1))
    return numbers


def normalize_page_ranges(
    ranges: Sequence[PageRangeInput],
) -> tuple[list[PageRangeInput], bool]:
    """Merge overlapping or duplicate ranges into their union (AC6).

    Only genuine overlaps (sharing at least one page) are merged; merely
    adjacent ranges (e.g. ``1-10`` and ``11-20``) are kept distinct since no
    page would otherwise be processed twice. Returns the merged, sorted
    list and whether any merge actually happened, so the caller can surface
    an explicit notice.
    """
    if not ranges:
        return [], False
    ordered = sorted(ranges, key=lambda r: (r.start_page, r.end_page))
    merged: list[PageRangeInput] = [ordered[0]]
    changed = False
    for current in ordered[1:]:
        last = merged[-1]
        if current.start_page <= last.end_page:
            changed = True
            if current.end_page > last.end_page:
                merged[-1] = PageRangeInput(last.start_page, current.end_page)
        else:
            merged.append(current)
    return merged, changed
