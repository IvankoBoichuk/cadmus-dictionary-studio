"""BH-54: manual lexeme-selection domain and application behavior."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    CreateLexemeService,
    DeleteLexemeService,
    DuplicateLexemeError,
    Lexeme,
    LexemeAccessError,
    LexemeEvent,
    LexemeEventType,
    LexemeInput,
    LexemeNotFoundError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeQueryService,
    LexemeValidationError,
    UpdateLexemeInput,
    UpdateLexemeService,
    changed_lexeme_fields,
    find_overlapping_lexeme,
    validate_lexeme_fields,
)
from cadmus.sources import (
    Dictionary,
    DictionaryPage,
    DictionaryPageRange,
    DictionaryStatus,
    GetDictionaryService,
    InspectionStatus,
    SourceFile,
)

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    """A minimal fake covering only what ``GetDictionaryService`` needs here."""

    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    page_ranges: dict[UUID, list[DictionaryPageRange]] = field(default_factory=dict)
    pages: dict[tuple[UUID, int], DictionaryPage] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self.source_files.get(dictionary_id)

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        return list(self.page_ranges.get(dictionary_id, []))

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        return self.pages.get((source_file_id, page_index))

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        return next((p for p in self.pages.values() if p.id == page_id), None)


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = repository

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
        pass


@dataclass
class MemoryLexicographyRepository:
    lexemes: dict[UUID, Lexeme] = field(default_factory=dict)
    events: list[LexemeEvent] = field(default_factory=list)

    def add_lexeme(self, lexeme: Lexeme) -> None:
        self.lexemes[lexeme.id] = lexeme

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]:
        return [lexeme for lexeme in self.lexemes.values() if lexeme.page_id == page_id]

    def get_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> Lexeme | None:
        lexeme = self.lexemes.get(lexeme_id)
        if lexeme is None or lexeme.dictionary_id != dictionary_id:
            return None
        return lexeme

    def update_lexeme(self, lexeme: Lexeme) -> None:
        self.lexemes[lexeme.id] = lexeme

    def delete_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> None:
        existing = self.lexemes.get(lexeme_id)
        if existing is not None and existing.dictionary_id == dictionary_id:
            del self.lexemes[lexeme_id]

    def add_lexeme_event(self, event: LexemeEvent) -> None:
        self.events.append(event)


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
        self.lexicography = repository
        self.committed = False

    def __enter__(self) -> "MemoryLexicographyUnitOfWork":
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


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
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
        "uploaded_at": NOW,
        "uploaded_by": dictionary_id,
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 400,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


def _page_range(
    dictionary_id: UUID, start: int, end: int, position: int = 0
) -> DictionaryPageRange:
    return DictionaryPageRange(
        id=uuid4(),
        dictionary_id=dictionary_id,
        start_page=start,
        end_page=end,
        position=position,
    )


def _page(
    source_file_id: UUID, page_index: int, width: int = 1000, height: int = 1400
) -> DictionaryPage:
    return DictionaryPage(
        id=uuid4(),
        source_file_id=source_file_id,
        page_index=page_index,
        processed_asset_key=f"sources/x/pages/{page_index:05d}.png",
        width=width,
        height=height,
        checksum_sha256="b" * 64,
        created_at=NOW,
    )


def _lexeme(page_id: UUID, x: float, y: float, width: float, height: float) -> Lexeme:
    return Lexeme(
        id=uuid4(),
        dictionary_id=uuid4(),
        page_id=page_id,
        source_text="слово",
        x=x,
        y=y,
        width=width,
        height=height,
        origin=LexemeOrigin.MANUAL,
        created_at=NOW,
        created_by=uuid4(),
        updated_at=NOW,
        updated_by=uuid4(),
    )


class Fixture:
    """Wires a dictionary + page + a ``GetDictionaryService`` for one test."""

    def __init__(self) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary
        self.source_file = _source_file(self.dictionary.id)
        self.sources_repository.source_files[self.dictionary.id] = self.source_file
        self.sources_repository.page_ranges[self.dictionary.id] = [
            _page_range(self.dictionary.id, 1, 5)
        ]
        self.page = _page(self.source_file.id, page_index=0)
        self.sources_repository.pages[(self.source_file.id, 0)] = self.page

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.create_service = CreateLexemeService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )
        self.query_service = LexemeQueryService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )
        self.update_service = UpdateLexemeService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )
        self.delete_service = DeleteLexemeService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )

    def create_lexeme(self, **overrides: object) -> Lexeme:
        defaults: dict[str, object] = {
            "page_number": 1,
            "source_text": "слово",
            "x": 10,
            "y": 10,
            "width": 100,
            "height": 40,
        }
        defaults.update(overrides)
        return self.create_service.create(
            self.dictionary.id,
            self.owner_id,
            LexemeInput(**defaults),  # type: ignore[arg-type]
        )


def test_validate_lexeme_fields_accepts_a_box_within_the_page() -> None:
    errors = validate_lexeme_fields(
        source_text="слово",
        x=10,
        y=10,
        width=100,
        height=40,
        page_width=1000,
        page_height=1400,
    )
    assert errors == {}


def test_validate_lexeme_fields_rejects_empty_text() -> None:
    errors = validate_lexeme_fields(
        source_text="   ",
        x=0,
        y=0,
        width=10,
        height=10,
        page_width=100,
        page_height=100,
    )
    assert "source_text" in errors


def test_validate_lexeme_fields_rejects_a_box_exceeding_the_page_bounds() -> None:
    errors = validate_lexeme_fields(
        source_text="слово",
        x=950,
        y=10,
        width=100,
        height=40,
        page_width=1000,
        page_height=1400,
    )
    assert "width" in errors


def test_find_overlapping_lexeme_detects_a_heavily_overlapping_box() -> None:
    page_id = uuid4()
    existing = [_lexeme(page_id, x=10, y=10, width=100, height=40)]

    overlap = find_overlapping_lexeme(
        x=15, y=12, width=90, height=35, existing=existing
    )

    assert overlap is existing[0]


def test_find_overlapping_lexeme_ignores_adjacent_non_overlapping_boxes() -> None:
    page_id = uuid4()
    existing = [_lexeme(page_id, x=10, y=10, width=100, height=40)]

    overlap = find_overlapping_lexeme(
        x=200, y=10, width=100, height=40, existing=existing
    )

    assert overlap is None


def test_create_lexeme_persists_a_manual_origin_lexeme() -> None:
    fixture = Fixture()

    lexeme = fixture.create_service.create(
        fixture.dictionary.id,
        fixture.owner_id,
        LexemeInput(
            page_number=1, source_text="слово", x=10, y=10, width=100, height=40
        ),
    )

    assert lexeme.origin is LexemeOrigin.MANUAL
    assert lexeme.dictionary_id == fixture.dictionary.id
    assert lexeme.page_id == fixture.page.id
    assert lexeme.created_by == fixture.owner_id
    stored = fixture.lexicography_repository.lexemes[lexeme.id]
    assert stored.source_text == "слово"


def test_create_lexeme_rejects_invalid_fields() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeValidationError) as error:
        fixture.create_service.create(
            fixture.dictionary.id,
            fixture.owner_id,
            LexemeInput(page_number=1, source_text="", x=0, y=0, width=10, height=10),
        )
    assert "source_text" in error.value.errors


def test_create_lexeme_out_of_range_page_number_raises_page_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(LexemePageNotFoundError):
        fixture.create_service.create(
            fixture.dictionary.id,
            fixture.owner_id,
            LexemeInput(
                page_number=99, source_text="слово", x=0, y=0, width=10, height=10
            ),
        )


def test_create_lexeme_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.create_service.create(
            fixture.dictionary.id,
            uuid4(),
            LexemeInput(
                page_number=1, source_text="слово", x=0, y=0, width=10, height=10
            ),
        )


def test_create_lexeme_flags_a_heavily_overlapping_reselection() -> None:
    fixture = Fixture()
    fixture.create_service.create(
        fixture.dictionary.id,
        fixture.owner_id,
        LexemeInput(
            page_number=1, source_text="слово", x=10, y=10, width=100, height=40
        ),
    )

    with pytest.raises(DuplicateLexemeError):
        fixture.create_service.create(
            fixture.dictionary.id,
            fixture.owner_id,
            LexemeInput(
                page_number=1, source_text="фраза", x=15, y=12, width=95, height=38
            ),
        )


def test_create_lexeme_confirm_duplicate_bypasses_the_overlap_check() -> None:
    fixture = Fixture()
    fixture.create_service.create(
        fixture.dictionary.id,
        fixture.owner_id,
        LexemeInput(
            page_number=1, source_text="слово", x=10, y=10, width=100, height=40
        ),
    )

    second = fixture.create_service.create(
        fixture.dictionary.id,
        fixture.owner_id,
        LexemeInput(
            page_number=1,
            source_text="фраза",
            x=15,
            y=12,
            width=95,
            height=38,
            confirm_duplicate=True,
        ),
    )

    assert len(fixture.lexicography_repository.lexemes) == 2
    assert second.source_text == "фраза"


def test_list_for_page_returns_only_that_page_s_lexemes() -> None:
    fixture = Fixture()
    fixture.create_service.create(
        fixture.dictionary.id,
        fixture.owner_id,
        LexemeInput(
            page_number=1, source_text="перше", x=10, y=10, width=100, height=40
        ),
    )

    lexemes = fixture.query_service.list_for_page(
        fixture.dictionary.id, fixture.owner_id, 1
    )

    assert len(lexemes) == 1
    assert lexemes[0].source_text == "перше"


def test_list_for_page_out_of_range_raises_page_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(LexemePageNotFoundError):
        fixture.query_service.list_for_page(fixture.dictionary.id, fixture.owner_id, 99)


def test_list_for_page_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.query_service.list_for_page(fixture.dictionary.id, uuid4(), 1)


def test_changed_lexeme_fields_reports_only_the_fields_that_differ() -> None:
    before = _lexeme(uuid4(), x=10, y=10, width=100, height=40)
    before.source_text = "старе"

    changed = changed_lexeme_fields(
        before, source_text="нове", x=10, y=10, width=100, height=40
    )

    assert changed == ["source_text"]


def test_changed_lexeme_fields_is_empty_when_nothing_changed() -> None:
    before = _lexeme(uuid4(), x=10, y=10, width=100, height=40)

    changed = changed_lexeme_fields(
        before,
        source_text=before.source_text,
        x=before.x,
        y=before.y,
        width=before.width,
        height=before.height,
    )

    assert changed == []


def test_update_lexeme_persists_text_and_box_changes() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme()

    updated = fixture.update_service.update(
        fixture.dictionary.id,
        lexeme.id,
        fixture.owner_id,
        UpdateLexemeInput(source_text="нове", x=20, y=20, width=120, height=50),
    )

    assert updated.source_text == "нове"
    assert (updated.x, updated.y, updated.width, updated.height) == (20, 20, 120, 50)
    assert updated.updated_by == fixture.owner_id
    stored = fixture.lexicography_repository.lexemes[lexeme.id]
    assert stored.source_text == "нове"


def test_update_lexeme_records_an_audit_event_with_changed_fields() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme(
        source_text="старе", x=10, y=10, width=100, height=40
    )

    fixture.update_service.update(
        fixture.dictionary.id,
        lexeme.id,
        fixture.owner_id,
        UpdateLexemeInput(source_text="нове", x=10, y=10, width=100, height=40),
    )

    assert len(fixture.lexicography_repository.events) == 1
    event = fixture.lexicography_repository.events[0]
    assert event.event_type is LexemeEventType.UPDATED
    assert event.lexeme_id == lexeme.id
    assert event.actor_user_id == fixture.owner_id
    assert event.changed_fields == ("source_text",)


def test_update_lexeme_is_a_no_op_when_nothing_actually_changed() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme(
        source_text="слово", x=10, y=10, width=100, height=40
    )

    fixture.update_service.update(
        fixture.dictionary.id,
        lexeme.id,
        fixture.owner_id,
        UpdateLexemeInput(source_text="слово", x=10, y=10, width=100, height=40),
    )

    assert fixture.lexicography_repository.events == []


def test_update_lexeme_rejects_a_box_exceeding_the_page_bounds() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme()

    with pytest.raises(LexemeValidationError) as error:
        fixture.update_service.update(
            fixture.dictionary.id,
            lexeme.id,
            fixture.owner_id,
            UpdateLexemeInput(source_text="слово", x=950, y=10, width=100, height=40),
        )
    assert "width" in error.value.errors


def test_update_lexeme_missing_lexeme_raises_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeNotFoundError):
        fixture.update_service.update(
            fixture.dictionary.id,
            uuid4(),
            fixture.owner_id,
            UpdateLexemeInput(source_text="слово", x=10, y=10, width=100, height=40),
        )


def test_update_lexeme_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme()

    with pytest.raises(LexemeAccessError):
        fixture.update_service.update(
            fixture.dictionary.id,
            lexeme.id,
            uuid4(),
            UpdateLexemeInput(source_text="слово", x=10, y=10, width=100, height=40),
        )


def test_delete_lexeme_removes_it_from_the_repository() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme()

    fixture.delete_service.delete(fixture.dictionary.id, lexeme.id, fixture.owner_id)

    assert lexeme.id not in fixture.lexicography_repository.lexemes


def test_delete_lexeme_records_an_audit_event() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme()

    fixture.delete_service.delete(fixture.dictionary.id, lexeme.id, fixture.owner_id)

    assert len(fixture.lexicography_repository.events) == 1
    event = fixture.lexicography_repository.events[0]
    assert event.event_type is LexemeEventType.DELETED
    assert event.lexeme_id == lexeme.id
    assert event.actor_user_id == fixture.owner_id


def test_delete_lexeme_missing_lexeme_raises_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeNotFoundError):
        fixture.delete_service.delete(fixture.dictionary.id, uuid4(), fixture.owner_id)


def test_delete_lexeme_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()
    lexeme = fixture.create_lexeme()

    with pytest.raises(LexemeAccessError):
        fixture.delete_service.delete(fixture.dictionary.id, lexeme.id, uuid4())
