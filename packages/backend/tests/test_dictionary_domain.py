from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cadmus.sources import (
    ContributorRole,
    Dictionary,
    DictionaryLanguage,
    DictionaryStatus,
    InspectionStatus,
    LegalStatus,
    PagesStatus,
    SourceFile,
    missing_required_fields,
    readiness_blockers,
)
from cadmus.sources.domain import (
    Contributor,
    apply_status_after_edit,
    normalize_isbn,
    validate_isbn,
    validate_legal_status,
    validate_publication_year,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _source_file(**overrides: object) -> SourceFile:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": uuid4(),
        "original_filename": "dictionary.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": "sources/owner/file.pdf",
        "uploaded_at": NOW,
        "uploaded_by": uuid4(),
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 3,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


def _dictionary(**overrides: object) -> Dictionary:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "status": DictionaryStatus.DRAFT,
        "created_at": NOW,
        "updated_at": NOW,
        "updated_by": uuid4(),
    }
    defaults.update(overrides)
    return Dictionary(**defaults)  # type: ignore[arg-type]


def test_missing_required_fields_reports_all_three_gaps_when_absent() -> None:
    dictionary = _dictionary()

    assert missing_required_fields(dictionary) == [
        "title",
        "languages",
        "legal_status",
    ]


def test_missing_required_fields_is_empty_once_all_three_are_set() -> None:
    dictionary = _dictionary(
        title="Словник української мови",
        legal_status=LegalStatus.PUBLIC_DOMAIN,
    )
    dictionary.languages = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code="uk", position=0
        )
    ]

    assert missing_required_fields(dictionary) == []


def test_missing_required_fields_treats_blank_title_as_missing() -> None:
    dictionary = _dictionary(title="   ")

    assert "title" in missing_required_fields(dictionary)


def _ready_dictionary(**overrides: object) -> Dictionary:
    dictionary = _dictionary(
        title="Словник української мови",
        legal_status=LegalStatus.PUBLIC_DOMAIN,
        **overrides,
    )
    dictionary.languages = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code="uk", position=0
        )
    ]
    return dictionary


def test_readiness_blockers_empty_once_metadata_and_source_are_ready() -> None:
    dictionary = _ready_dictionary()

    assert readiness_blockers(dictionary, _source_file()) == []


def test_readiness_blockers_reports_missing_source_file() -> None:
    dictionary = _ready_dictionary()

    blockers = readiness_blockers(dictionary, None)

    assert [b.code for b in blockers] == ["source_missing"]


def test_readiness_blockers_reports_unverified_source() -> None:
    dictionary = _ready_dictionary()
    source = _source_file(inspection_status=InspectionStatus.PENDING)

    blockers = readiness_blockers(dictionary, source)

    assert [b.code for b in blockers] == ["source_not_verified"]


def test_readiness_blockers_reports_failed_source() -> None:
    dictionary = _ready_dictionary()
    source = _source_file(inspection_status=InspectionStatus.FAILED)

    blockers = readiness_blockers(dictionary, source)

    assert [b.code for b in blockers] == ["source_invalid"]


def test_readiness_blockers_combines_metadata_and_source_gaps() -> None:
    dictionary = _dictionary()

    blockers = readiness_blockers(dictionary, None)

    assert [b.code for b in blockers] == [
        "title",
        "languages",
        "legal_status",
        "source_missing",
    ]


def test_apply_status_after_edit_reverts_configured_dictionary_with_blockers() -> None:
    dictionary = _ready_dictionary(status=DictionaryStatus.CONFIGURED)

    reverted = apply_status_after_edit(dictionary, readiness_blockers(dictionary, None))

    assert reverted is True
    assert dictionary.status is DictionaryStatus.DRAFT


def test_apply_status_after_edit_leaves_configured_untouched_when_ready() -> None:
    dictionary = _ready_dictionary(status=DictionaryStatus.CONFIGURED)

    reverted = apply_status_after_edit(
        dictionary, readiness_blockers(dictionary, _source_file())
    )

    assert reverted is False
    assert dictionary.status is DictionaryStatus.CONFIGURED


def test_apply_status_after_edit_leaves_draft_dictionary_untouched() -> None:
    dictionary = _dictionary()

    reverted = apply_status_after_edit(dictionary, readiness_blockers(dictionary, None))

    assert reverted is False
    assert dictionary.status is DictionaryStatus.DRAFT


def test_readiness_blockers_treats_a_plain_string_inspection_status_as_verified() -> (
    None
):
    """SQLAlchemy's String-column mapping returns a plain str, not the enum

    member, once a row is freshly loaded from the database; ``==`` (not
    ``is``) must be used so a verified source is recognized either way.
    """
    dictionary = _ready_dictionary()
    source = _source_file()
    source.inspection_status = "verified"  # type: ignore[assignment]

    assert readiness_blockers(dictionary, source) == []


def test_apply_status_after_edit_treats_a_plain_string_status_as_configured() -> None:
    dictionary = _ready_dictionary()
    dictionary.status = "configured"  # type: ignore[assignment]

    reverted = apply_status_after_edit(dictionary, readiness_blockers(dictionary, None))

    assert reverted is True
    assert dictionary.status is DictionaryStatus.DRAFT


@pytest.mark.parametrize(
    ("year", "current_year", "valid"),
    [
        (1993, 2026, True),
        (1450, 2026, True),
        (2027, 2026, True),
        (1449, 2026, False),
        (2028, 2026, False),
        (0, 2026, False),
    ],
)
def test_validate_publication_year(year: int, current_year: int, valid: bool) -> None:
    error = validate_publication_year(year, current_year=current_year)
    assert (error is None) == valid


def test_normalize_isbn_strips_formatting_and_upper_cases_checksum() -> None:
    assert normalize_isbn("0-306-40615-x") == "030640615X"
    assert normalize_isbn(" 978 0306406157 ") == "9780306406157"


@pytest.mark.parametrize(
    ("raw", "valid"),
    [
        ("0-306-40615-2", True),
        ("0306406152", True),
        ("978-0-306-40615-7", True),
        ("9780306406157", True),
        ("0306406153", False),
        ("1234567890123", False),
        ("not-an-isbn", False),
        ("12345", False),
    ],
)
def test_validate_isbn_checksum(raw: str, valid: bool) -> None:
    _, error = validate_isbn(raw)
    assert (error is None) == valid


def test_validate_legal_status_requires_license_type_when_licensed() -> None:
    errors = validate_legal_status(LegalStatus.LICENSED, None, None)
    assert "license_type" in errors

    assert validate_legal_status(LegalStatus.LICENSED, "CC-BY-4.0", None) == {}


def test_validate_legal_status_requires_permission_reference_when_granted() -> None:
    errors = validate_legal_status(LegalStatus.PERMISSION_GRANTED, None, None)
    assert "permission_reference" in errors

    assert (
        validate_legal_status(LegalStatus.PERMISSION_GRANTED, None, "letter-2026-08-01")
        == {}
    )


@pytest.mark.parametrize(
    "legal_status",
    [LegalStatus.PUBLIC_DOMAIN, LegalStatus.RESTRICTED, LegalStatus.UNKNOWN],
)
def test_validate_legal_status_has_no_conditional_fields_for_other_statuses(
    legal_status: LegalStatus,
) -> None:
    assert validate_legal_status(legal_status, None, None) == {}


def test_mark_pages_completed_clears_a_prior_error() -> None:
    source_file = _source_file(pages_status=PagesStatus.FAILED, pages_error="boom")

    source_file.mark_pages_completed()

    assert source_file.pages_status is PagesStatus.COMPLETED
    assert source_file.pages_error is None


def test_mark_pages_failed_records_the_reason() -> None:
    source_file = _source_file()

    source_file.mark_pages_failed("Stored PDF object is missing.")

    assert source_file.pages_status is PagesStatus.FAILED
    assert source_file.pages_error == "Stored PDF object is missing."


def test_mark_pages_failed_does_not_downgrade_a_completed_split() -> None:
    source_file = _source_file(pages_status=PagesStatus.COMPLETED)

    source_file.mark_pages_failed("retry raced a completed split")

    assert source_file.pages_status is PagesStatus.COMPLETED
    assert source_file.pages_error is None


def test_contributor_role_enum_supports_author_and_compiler() -> None:
    contributor = Contributor(
        id=uuid4(),
        dictionary_id=uuid4(),
        name="Борис Грінченко",
        role=ContributorRole.COMPILER,
        position=0,
    )
    assert contributor.role is ContributorRole.COMPILER
