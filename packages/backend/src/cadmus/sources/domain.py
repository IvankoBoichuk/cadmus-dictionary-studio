"""Sources domain objects and invariants for the dictionary draft aggregate."""

import re
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
    """Configuration-readiness status owned by this Story (and BH-31)."""

    DRAFT = "draft"
    CONFIGURED = "configured"


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


class InspectionStatus(StrEnum):
    """Lifecycle of the asynchronous, worker-side PDF structural inspection."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class DictionaryEventType(StrEnum):
    """Append-only audit event kinds."""

    CREATED = "created"
    SOURCE_UPLOADED = "source_uploaded"
    METADATA_UPDATED = "metadata_updated"


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


@dataclass
class DictionaryEvent:
    """One append-only provenance/audit entry for a dictionary draft."""

    id: UUID
    dictionary_id: UUID
    event_type: DictionaryEventType
    actor_user_id: UUID
    occurred_at: datetime
    changed_fields: tuple[str, ...] = ()


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
