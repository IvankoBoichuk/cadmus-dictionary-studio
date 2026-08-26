from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.sources import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    Contributor,
    ContributorInput,
    ContributorRole,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryEventType,
    DictionaryLanguage,
    DictionaryNotReadyError,
    DictionaryPage,
    DictionaryPageRange,
    DictionaryReadinessService,
    DictionarySettlementMapping,
    DictionaryStatus,
    InspectionStatus,
    LegalStatus,
    MetadataInput,
    MetadataValidationError,
    SaveDictionaryMetadataService,
    SourceFile,
)

FIRST_SAVE = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
SECOND_SAVE = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    contributors: dict[UUID, list[Contributor]] = field(default_factory=dict)
    languages: dict[UUID, list[DictionaryLanguage]] = field(default_factory=dict)
    events: list[DictionaryEvent] = field(default_factory=list)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    page_ranges: dict[UUID, list[DictionaryPageRange]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        dictionary = self.dictionaries.get(dictionary_id)
        if dictionary is None:
            return None
        dictionary.contributors = list(self.contributors.get(dictionary_id, []))
        dictionary.languages = list(self.languages.get(dictionary_id, []))
        return dictionary

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self.source_files.get(dictionary_id)

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        return None

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by metadata save")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.dictionary_id] = source_file

    def update_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.dictionary_id] = source_file

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        self.contributors[dictionary_id] = list(contributors)

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        self.languages[dictionary_id] = list(languages)

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        return list(self.page_ranges.get(dictionary_id, []))

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None:
        self.page_ranges[dictionary_id] = list(ranges)

    def add_event(self, event: DictionaryEvent) -> None:
        self.events.append(event)

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by metadata save")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by metadata save")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by metadata save")

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        raise AssertionError("not used by metadata save")

    def list_pages(self, source_file_id: UUID) -> list[DictionaryPage]:
        raise AssertionError("not used by metadata save")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by metadata save")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by metadata save")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by metadata save")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by metadata save")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by metadata save")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by metadata save")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by metadata save")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by metadata save")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by metadata save")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by metadata save")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by metadata save")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by metadata save")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by metadata save")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by metadata save")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by metadata save")


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = repository
        self.committed = False

    def __enter__(self) -> "MemorySourcesUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True


def _draft(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=FIRST_SAVE,
        updated_at=FIRST_SAVE,
        updated_by=owner_id,
    )


def _service(
    repository: MemorySourcesRepository, clock: datetime = FIRST_SAVE
) -> SaveDictionaryMetadataService:
    return SaveDictionaryMetadataService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: clock,
    )


def _readiness_service(
    repository: MemorySourcesRepository, clock: datetime = FIRST_SAVE
) -> DictionaryReadinessService:
    return DictionaryReadinessService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: clock,
    )


def _source_file(dictionary_id: UUID, **overrides: object) -> SourceFile:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": dictionary_id,
        "original_filename": "dictionary.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": f"sources/{dictionary_id}/file.pdf",
        "uploaded_at": FIRST_SAVE,
        "uploaded_by": dictionary_id,
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 3,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


def _minimal_input(**overrides: object) -> MetadataInput:
    defaults: dict[str, object] = {
        "title": "Словник української мови",
        "description": None,
        "dictionary_type": None,
        "publisher": None,
        "publication_year": None,
        "article_description": None,
        "edition": None,
        "isbn": None,
        "digital_source": None,
        "legal_status": LegalStatus.PUBLIC_DOMAIN,
        "license_type": None,
        "permission_reference": None,
        "rights_note": None,
        "contributors": (),
        "language_codes": ("uk",),
    }
    defaults.update(overrides)
    return MetadataInput(**defaults)  # type: ignore[arg-type]


def test_saving_complete_metadata_leaves_no_missing_required_fields() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    outcome = service.save(dictionary.id, owner_id, _minimal_input())

    assert outcome.missing_required_fields == []
    assert outcome.dictionary.title == "Словник української мови"


def test_saving_incomplete_metadata_is_allowed_and_reports_gaps() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    outcome = service.save(
        dictionary.id,
        owner_id,
        _minimal_input(title=None, legal_status=None, language_codes=()),
    )

    assert outcome.dictionary.status is DictionaryStatus.DRAFT
    assert set(outcome.missing_required_fields) == {
        "title",
        "languages",
        "legal_status",
    }


def test_contributors_are_stored_ordered_and_structured() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    service.save(
        dictionary.id,
        owner_id,
        _minimal_input(
            contributors=(
                ContributorInput(name="Борис Грінченко", role=ContributorRole.COMPILER),
                ContributorInput(name="Марія Загірня", role=ContributorRole.AUTHOR),
            )
        ),
    )

    stored = repository.contributors[dictionary.id]
    assert [c.name for c in stored] == ["Борис Грінченко", "Марія Загірня"]
    assert [c.position for c in stored] == [0, 1]
    assert stored[1].role is ContributorRole.AUTHOR


def test_reordering_contributors_on_a_second_save_replaces_the_ordered_list() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    a = ContributorInput(name="A", role=ContributorRole.AUTHOR)
    b = ContributorInput(name="B", role=ContributorRole.AUTHOR)
    service.save(dictionary.id, owner_id, _minimal_input(contributors=(a, b)))

    service.save(dictionary.id, owner_id, _minimal_input(contributors=(b, a)))

    stored = repository.contributors[dictionary.id]
    assert [c.name for c in stored] == ["B", "A"]
    assert [c.position for c in stored] == [0, 1]


def test_multiple_languages_are_stored_structurally() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    service.save(
        dictionary.id, owner_id, _minimal_input(language_codes=("uk", "en", "de"))
    )

    stored = repository.languages[dictionary.id]
    assert [entry.language_code for entry in stored] == ["uk", "en", "de"]


def test_unknown_language_code_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(MetadataValidationError) as error:
        service.save(dictionary.id, owner_id, _minimal_input(language_codes=("zz",)))
    assert "language_codes" in error.value.errors


@pytest.mark.parametrize(
    "legal_status",
    [
        LegalStatus.PUBLIC_DOMAIN,
        LegalStatus.LICENSED,
        LegalStatus.PERMISSION_GRANTED,
        LegalStatus.RESTRICTED,
        LegalStatus.UNKNOWN,
    ],
)
def test_every_legal_status_can_be_saved_with_its_conditional_fields(
    legal_status: LegalStatus,
) -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    extra: dict[str, object] = {}
    if legal_status is LegalStatus.LICENSED:
        extra["license_type"] = "CC-BY-4.0"
    if legal_status is LegalStatus.PERMISSION_GRANTED:
        extra["permission_reference"] = "letter-2026-08-01"

    outcome = service.save(
        dictionary.id, owner_id, _minimal_input(legal_status=legal_status, **extra)
    )

    assert outcome.dictionary.legal_status is legal_status


def test_licensed_status_without_license_type_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(MetadataValidationError) as error:
        service.save(
            dictionary.id,
            owner_id,
            _minimal_input(legal_status=LegalStatus.LICENSED),
        )
    assert "license_type" in error.value.errors


def test_permission_granted_without_reference_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(MetadataValidationError) as error:
        service.save(
            dictionary.id,
            owner_id,
            _minimal_input(legal_status=LegalStatus.PERMISSION_GRANTED),
        )
    assert "permission_reference" in error.value.errors


@pytest.mark.parametrize(("year", "valid"), [(1993, True), (999, False), (2999, False)])
def test_publication_year_validation(year: int, valid: bool) -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository, clock=FIRST_SAVE)

    if valid:
        outcome = service.save(
            dictionary.id, owner_id, _minimal_input(publication_year=year)
        )
        assert outcome.dictionary.publication_year == year
    else:
        with pytest.raises(MetadataValidationError) as error:
            service.save(dictionary.id, owner_id, _minimal_input(publication_year=year))
        assert "publication_year" in error.value.errors


def test_isbn_is_normalized_and_validated() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    outcome = service.save(
        dictionary.id, owner_id, _minimal_input(isbn="0-306-40615-2")
    )

    assert outcome.dictionary.isbn == "0306406152"


def test_invalid_isbn_checksum_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(MetadataValidationError) as error:
        service.save(dictionary.id, owner_id, _minimal_input(isbn="0306406153"))
    assert "isbn" in error.value.errors


def test_editing_metadata_preserves_dictionary_id_and_updates_audit_fields() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository, clock=FIRST_SAVE)
    first = service.save(dictionary.id, owner_id, _minimal_input(title="Draft title"))
    assert first.dictionary.updated_at == FIRST_SAVE

    later_service = _service(repository, clock=SECOND_SAVE)
    second = later_service.save(
        dictionary.id, owner_id, _minimal_input(title="Final title")
    )

    assert second.dictionary.id == first.dictionary.id
    assert second.dictionary.title == "Final title"
    assert second.dictionary.updated_at == SECOND_SAVE
    assert second.dictionary.updated_by == owner_id
    event_types = [event.event_type for event in repository.events]
    assert event_types.count(DictionaryEventType.METADATA_UPDATED) == 2
    assert "title" in repository.events[-1].changed_fields


def test_actor_other_than_owner_cannot_save_metadata() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.save(dictionary.id, uuid4(), _minimal_input())


def test_saving_missing_dictionary_raises_access_error_not_found() -> None:
    repository = MemorySourcesRepository()
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.save(uuid4(), uuid4(), _minimal_input())


def _ready_draft(owner_id: UUID, repository: MemorySourcesRepository) -> Dictionary:
    """A draft with complete BH-27 metadata, a verified source (BH-31 AC5),

    and a BH-28 page range -- everything ``readiness_blockers`` requires.
    """
    dictionary = _draft(owner_id)
    dictionary.title = "Словник української мови"
    dictionary.legal_status = LegalStatus.PUBLIC_DOMAIN
    repository.add_dictionary(dictionary)
    repository.languages[dictionary.id] = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code="uk", position=0
        )
    ]
    repository.source_files[dictionary.id] = _source_file(dictionary.id)
    repository.page_ranges[dictionary.id] = [
        DictionaryPageRange(
            id=uuid4(),
            dictionary_id=dictionary.id,
            start_page=1,
            end_page=3,
            position=0,
        )
    ]
    return dictionary


def test_confirm_configured_transitions_a_ready_draft() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    service = _readiness_service(repository, clock=SECOND_SAVE)

    configured = service.confirm_configured(dictionary.id, owner_id)

    assert configured.status is DictionaryStatus.CONFIGURED
    assert configured.updated_at == SECOND_SAVE
    assert repository.dictionaries[dictionary.id].status is DictionaryStatus.CONFIGURED


def test_confirm_configured_records_a_status_changed_event() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    service = _readiness_service(repository, clock=SECOND_SAVE)

    service.confirm_configured(dictionary.id, owner_id)

    assert len(repository.events) == 1
    event = repository.events[0]
    assert event.event_type is DictionaryEventType.STATUS_CHANGED
    assert event.previous_status is DictionaryStatus.DRAFT
    assert event.new_status is DictionaryStatus.CONFIGURED
    assert event.actor_user_id == owner_id


def test_confirm_configured_rejects_incomplete_metadata_and_leaves_draft() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _draft(owner_id)
    repository.add_dictionary(dictionary)
    repository.source_files[dictionary.id] = _source_file(dictionary.id)
    service = _readiness_service(repository)

    with pytest.raises(DictionaryNotReadyError) as error:
        service.confirm_configured(dictionary.id, owner_id)

    codes = {blocker.code for blocker in error.value.blockers}
    assert {"title", "languages", "legal_status"} <= codes
    assert repository.dictionaries[dictionary.id].status is DictionaryStatus.DRAFT
    assert repository.events == []


def test_confirm_configured_rejects_missing_source() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    del repository.source_files[dictionary.id]
    service = _readiness_service(repository)

    with pytest.raises(DictionaryNotReadyError) as error:
        service.confirm_configured(dictionary.id, owner_id)

    assert [b.code for b in error.value.blockers] == ["source_missing"]


def test_confirm_configured_records_previous_status_from_a_plain_string() -> None:
    """Regression: a freshly DB-loaded ``status`` is a plain str, not the enum
    member; the recorded ``previous_status`` must still normalize correctly.
    """
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    dictionary.status = "draft"  # type: ignore[assignment]
    service = _readiness_service(repository, clock=SECOND_SAVE)

    service.confirm_configured(dictionary.id, owner_id)

    assert repository.events[0].previous_status is DictionaryStatus.DRAFT


def test_confirm_configured_actor_other_than_owner_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    service = _readiness_service(repository)

    with pytest.raises(DictionaryAccessError):
        service.confirm_configured(dictionary.id, uuid4())


def test_saving_metadata_that_breaks_readiness_reverts_configured_to_draft() -> None:
    """BH-31 AC7: editing never blocks, but an invalid configured draft demotes."""
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    dictionary.status = DictionaryStatus.CONFIGURED
    service = _service(repository, clock=SECOND_SAVE)

    outcome = service.save(dictionary.id, owner_id, _minimal_input(legal_status=None))

    assert outcome.dictionary.status is DictionaryStatus.DRAFT
    status_events = [
        event
        for event in repository.events
        if event.event_type is DictionaryEventType.STATUS_CHANGED
    ]
    assert len(status_events) == 1
    assert status_events[0].previous_status is DictionaryStatus.CONFIGURED
    assert status_events[0].new_status is DictionaryStatus.DRAFT
    assert status_events[0].reason == "metadata_no_longer_ready"


def test_saving_metadata_that_keeps_readiness_valid_leaves_configured_status() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _ready_draft(owner_id, repository)
    dictionary.status = DictionaryStatus.CONFIGURED
    service = _service(repository, clock=SECOND_SAVE)

    outcome = service.save(dictionary.id, owner_id, _minimal_input(title="Новий"))

    assert outcome.dictionary.status is DictionaryStatus.CONFIGURED
    status_events = [
        event
        for event in repository.events
        if event.event_type is DictionaryEventType.STATUS_CHANGED
    ]
    assert status_events == []
