"""Manual entry-field CRUD and rule-based abbreviation/geography tagging (BH-148)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    ArticleSchema,
    CreateEntryFieldService,
    DeleteEntryFieldService,
    EntryField,
    EntryFieldAccessError,
    EntryFieldOrigin,
    EntryFieldRole,
    EntryFieldValidationError,
    LexicographyRepository,
    RuleBasedAnnotationService,
    SchemaGenerationStatus,
    UpdateEntryFieldService,
)
from cadmus.sources import (
    Abbreviation,
    AbbreviationCategory,
    Dictionary,
    DictionarySettlementMapping,
    DictionaryStatus,
    SettlementMappingStatus,
    SourcesRepository,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 26, 13, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    abbreviations: dict[UUID, list[Abbreviation]] = field(default_factory=dict)
    settlements: dict[UUID, list[DictionarySettlementMapping]] = field(
        default_factory=dict
    )

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        return list(self.abbreviations.get(dictionary_id, []))

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        return list(self.settlements.get(dictionary_id, []))


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = cast(SourcesRepository, repository)

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
    fields: dict[UUID, list[EntryField]] = field(default_factory=dict)

    def add_field(self, entry_field: EntryField) -> None:
        self.fields.setdefault(entry_field.entry_id, []).append(entry_field)

    def list_fields_for_entry(self, entry_id: UUID) -> list[EntryField]:
        return list(self.fields.get(entry_id, []))

    def update_field(self, entry_field: EntryField) -> None:
        bucket = self.fields.setdefault(entry_field.entry_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == entry_field.id:
                bucket[index] = entry_field
                return

    def delete_field(self, field_id: UUID) -> None:
        for bucket in self.fields.values():
            bucket[:] = [f for f in bucket if f.id != field_id]

    def get_entry(self, entry_id: UUID) -> None:
        # CRUD services only need dictionary-level authorization here; the
        # entry itself is resolved by ``_EntryFieldWriteService._authorize``.
        raise AssertionError("not used directly by these tests")


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
        self.lexicography = cast(LexicographyRepository, repository)

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
        pass


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _field(
    entry_id: UUID,
    fragment_id: UUID,
    source_text: str = "значення слова",
    role: EntryFieldRole = EntryFieldRole.MEANING,
    origin: EntryFieldOrigin = EntryFieldOrigin.MODEL,
) -> EntryField:
    return EntryField(
        id=uuid4(),
        entry_id=entry_id,
        fragment_id=fragment_id,
        field_path="meaning[0]",
        role=role,
        position=0,
        source_text=source_text,
        source_start=0,
        source_end=len(source_text),
        origin=origin,
        created_at=NOW,
        created_by=entry_id,
        updated_at=NOW,
        updated_by=entry_id,
    )


class _EntryFieldFixture:
    """Uses a real ``DictionaryEntry``-free authorize path: the CRUD write
    services only need ``GetDictionaryService`` for the dictionary owning
    the entry, resolved from an entry fetched via ``get_entry`` -- so this
    fixture patches ``get_entry`` to return a fixed dictionary id.
    """

    def __init__(self) -> None:
        from cadmus.lexicography import DictionaryEntry, EntryStatus
        from cadmus.sources import GetDictionaryService

        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.entry_id = uuid4()
        self._entry = DictionaryEntry(
            id=self.entry_id,
            dictionary_id=self.dictionary.id,
            lexeme_id=uuid4(),
            headword="слово",
            status=EntryStatus.DRAFT,
            created_at=NOW,
            updated_at=NOW,
            created_by=self.owner_id,
            updated_by=self.owner_id,
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.lexicography_repository.get_entry = lambda entry_id: (  # type: ignore[method-assign,assignment]
            self._entry if entry_id == self.entry_id else None
        )
        self.fragment_id = uuid4()

        self.create_service = CreateEntryFieldService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            clock=lambda: LATER,
        )
        self.update_service = UpdateEntryFieldService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            clock=lambda: LATER,
        )
        self.delete_service = DeleteEntryFieldService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )


def test_create_entry_field_persists_a_manual_field() -> None:
    fixture = _EntryFieldFixture()

    created = fixture.create_service.create(
        fixture.entry_id,
        fixture.owner_id,
        fragment_id=fixture.fragment_id,
        field_path="synonym[0]",
        role=EntryFieldRole.SYNONYM,
        source_text="приклад",
        source_start=0,
        source_end=7,
    )

    assert created.origin is EntryFieldOrigin.MANUAL
    stored = fixture.lexicography_repository.list_fields_for_entry(fixture.entry_id)
    assert [f.id for f in stored] == [created.id]


def test_create_entry_field_rejects_blank_text() -> None:
    from cadmus.lexicography import EntryFieldValidationError

    fixture = _EntryFieldFixture()

    with pytest.raises(EntryFieldValidationError):
        fixture.create_service.create(
            fixture.entry_id,
            fixture.owner_id,
            fragment_id=fixture.fragment_id,
            field_path="synonym[0]",
            role=EntryFieldRole.SYNONYM,
            source_text="   ",
            source_start=0,
            source_end=0,
        )


def _attach_enum_schema(fixture: _EntryFieldFixture, options: list[str]) -> None:
    schema = ArticleSchema(
        id=uuid4(),
        dictionary_id=fixture.dictionary.id,
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={
            "fields": [
                {
                    "name": "gender",
                    "role": "other",
                    "type": "enum",
                    "options": options,
                }
            ]
        },
        created_at=NOW,
        created_by=fixture.owner_id,
    )
    fixture._entry.schema_id = schema.id
    fixture.lexicography_repository.get_article_schema = (  # type: ignore[attr-defined]
        lambda schema_id: schema if schema_id == schema.id else None
    )


def test_create_entry_field_rejects_value_outside_enum_options() -> None:
    fixture = _EntryFieldFixture()
    _attach_enum_schema(fixture, ["ч.", "ж.", "с."])  # noqa: RUF001

    with pytest.raises(EntryFieldValidationError):
        fixture.create_service.create(
            fixture.entry_id,
            fixture.owner_id,
            fragment_id=fixture.fragment_id,
            field_path="gender",
            role=EntryFieldRole.OTHER,
            source_text="мн.",
            source_start=0,
            source_end=0,
        )


def test_create_entry_field_accepts_value_in_enum_options() -> None:
    fixture = _EntryFieldFixture()
    _attach_enum_schema(fixture, ["ч.", "ж.", "с."])  # noqa: RUF001

    created = fixture.create_service.create(
        fixture.entry_id,
        fixture.owner_id,
        fragment_id=fixture.fragment_id,
        field_path="gender",
        role=EntryFieldRole.OTHER,
        source_text="ж.",
        source_start=0,
        source_end=0,
    )

    assert created.source_text == "ж."


def _attach_reference_schema(fixture: _EntryFieldFixture, node_type: str) -> None:
    schema = ArticleSchema(
        id=uuid4(),
        dictionary_id=fixture.dictionary.id,
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={
            "fields": [
                {"name": "tag", "role": node_type, "type": node_type, "options": []}
            ]
        },
        created_at=NOW,
        created_by=fixture.owner_id,
    )
    fixture._entry.schema_id = schema.id
    fixture.lexicography_repository.get_article_schema = (  # type: ignore[attr-defined]
        lambda schema_id: schema if schema_id == schema.id else None
    )


@pytest.mark.parametrize("node_type", ["abbreviation", "geographic_label"])
def test_create_entry_field_accepts_any_value_for_reference_types(
    node_type: str,
) -> None:
    fixture = _EntryFieldFixture()
    _attach_reference_schema(fixture, node_type)

    created = fixture.create_service.create(
        fixture.entry_id,
        fixture.owner_id,
        fragment_id=fixture.fragment_id,
        field_path="tag",
        role=EntryFieldRole.OTHER,
        source_text="не з довідника",
        source_start=0,
        source_end=0,
    )

    assert created.source_text == "не з довідника"


def test_update_entry_field_rejects_normalized_text_outside_enum_options() -> None:
    fixture = _EntryFieldFixture()
    _attach_enum_schema(fixture, ["ч.", "ж.", "с."])  # noqa: RUF001
    existing = _field(
        fixture.entry_id, fixture.fragment_id, origin=EntryFieldOrigin.MODEL
    )
    existing.field_path = "gender"
    fixture.lexicography_repository.add_field(existing)

    with pytest.raises(EntryFieldValidationError):
        fixture.update_service.update(
            fixture.entry_id,
            existing.id,
            fixture.owner_id,
            normalized_text="не-опція",
        )


def test_update_entry_field_flips_origin_to_manual_and_stamps_updater() -> None:
    fixture = _EntryFieldFixture()
    existing = _field(
        fixture.entry_id, fixture.fragment_id, origin=EntryFieldOrigin.MODEL
    )
    fixture.lexicography_repository.add_field(existing)

    updated = fixture.update_service.update(
        fixture.entry_id,
        existing.id,
        fixture.owner_id,
        source_text="виправлене значення",
    )

    assert updated.origin is EntryFieldOrigin.MANUAL
    assert updated.updated_by == fixture.owner_id
    assert updated.updated_at == LATER
    assert updated.source_text == "виправлене значення"


def test_update_entry_field_unknown_field_raises_access_error() -> None:
    fixture = _EntryFieldFixture()

    with pytest.raises(EntryFieldAccessError):
        fixture.update_service.update(fixture.entry_id, uuid4(), fixture.owner_id)


def test_delete_entry_field_removes_it() -> None:
    fixture = _EntryFieldFixture()
    existing = _field(fixture.entry_id, fixture.fragment_id)
    fixture.lexicography_repository.add_field(existing)

    fixture.delete_service.delete(fixture.entry_id, existing.id, fixture.owner_id)

    assert fixture.lexicography_repository.list_fields_for_entry(fixture.entry_id) == []


def test_delete_entry_field_unknown_field_raises_access_error() -> None:
    fixture = _EntryFieldFixture()

    with pytest.raises(EntryFieldAccessError):
        fixture.delete_service.delete(fixture.entry_id, uuid4(), fixture.owner_id)


# --- RuleBasedAnnotationService ----------------------------------------------


def _abbreviation(dictionary_id: UUID, text: str) -> Abbreviation:
    return Abbreviation(
        id=uuid4(),
        dictionary_id=dictionary_id,
        abbreviation=text,
        category=AbbreviationCategory.GRAMMAR,
        unresolved=False,
        created_at=NOW,
        updated_at=NOW,
        created_by=dictionary_id,
        updated_by=dictionary_id,
    )


def _settlement(
    dictionary_id: UUID,
    label: str,
    *,
    modern_settlement_name: str | None = None,
    community_name: str | None = None,
    district: str | None = None,
) -> DictionarySettlementMapping:
    return DictionarySettlementMapping(
        id=uuid4(),
        dictionary_id=dictionary_id,
        source_label=label,
        status=SettlementMappingStatus.UNRESOLVED,
        created_at=NOW,
        updated_at=NOW,
        created_by=dictionary_id,
        updated_by=dictionary_id,
        modern_settlement_name=modern_settlement_name,
        community_name=community_name,
        district=district,
    )


class _AnnotationFixture:
    def __init__(self) -> None:
        from cadmus.sources import GetDictionaryService

        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary
        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.entry_id = uuid4()
        self.fragment_id = uuid4()
        self.service = RuleBasedAnnotationService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            sources_unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            ),
            clock=lambda: LATER,
        )


def test_tag_abbreviations_and_geography_creates_child_fields() -> None:
    fixture = _AnnotationFixture()
    fixture.sources_repository.abbreviations[fixture.dictionary.id] = [
        _abbreviation(fixture.dictionary.id, "розм.")
    ]
    fixture.sources_repository.settlements[fixture.dictionary.id] = [
        _settlement(fixture.dictionary.id, "Львів")
    ]
    parent = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text="слово розм., вживається у Львів.",  # noqa: RUF001
    )
    fixture.lexicography_repository.add_field(parent)

    created = fixture.service.tag_abbreviations_and_geography(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    roles = {tag.role for tag in created}
    assert EntryFieldRole.ABBREVIATION in roles
    assert EntryFieldRole.GEOGRAPHIC_LABEL in roles
    for tag in created:
        assert tag.origin is EntryFieldOrigin.RULE
        assert tag.parent_field_id == parent.id


def test_tag_abbreviations_and_geography_is_case_insensitive() -> None:
    fixture = _AnnotationFixture()
    fixture.sources_repository.abbreviations[fixture.dictionary.id] = [
        _abbreviation(fixture.dictionary.id, "РОЗМ.")  # noqa: RUF001
    ]
    parent = _field(fixture.entry_id, fixture.fragment_id, source_text="це розм. слово")
    fixture.lexicography_repository.add_field(parent)

    created = fixture.service.tag_abbreviations_and_geography(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    assert len(created) == 1
    assert created[0].role is EntryFieldRole.ABBREVIATION


def test_tag_abbreviations_and_geography_skips_fields_already_tagged_by_rule() -> None:
    fixture = _AnnotationFixture()
    fixture.sources_repository.abbreviations[fixture.dictionary.id] = [
        _abbreviation(fixture.dictionary.id, "розм.")
    ]
    already_tagged = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text="розм.",
        origin=EntryFieldOrigin.RULE,
    )
    fixture.lexicography_repository.add_field(already_tagged)

    created = fixture.service.tag_abbreviations_and_geography(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    assert created == []


def test_tag_abbreviations_and_geography_skips_a_field_that_is_the_abbreviation() -> (
    None
):
    fixture = _AnnotationFixture()
    fixture.sources_repository.abbreviations[fixture.dictionary.id] = [
        _abbreviation(fixture.dictionary.id, "ж.")
    ]
    # a MODEL field whose entire value already *is* the abbreviation -- it must
    # not spawn a redundant "<path>.abbreviation" child
    whole = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text=" ж. ",
        origin=EntryFieldOrigin.MODEL,
    )
    inside = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text="вживається ж. у розмові",  # noqa: RUF001
        origin=EntryFieldOrigin.MODEL,
    )
    fixture.lexicography_repository.add_field(whole)
    fixture.lexicography_repository.add_field(inside)

    created = fixture.service.tag_abbreviations_and_geography(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    assert len(created) == 1
    assert created[0].parent_field_id == inside.id


def test_tag_abbreviations_and_geography_returns_empty_without_reference_data() -> None:
    fixture = _AnnotationFixture()
    parent = _field(
        fixture.entry_id, fixture.fragment_id, source_text="звичайний текст"
    )
    fixture.lexicography_repository.add_field(parent)

    created = fixture.service.tag_abbreviations_and_geography(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    assert created == []


def test_resolve_geographic_labels_links_a_field_to_its_mapping() -> None:
    fixture = _AnnotationFixture()
    fixture.sources_repository.settlements[fixture.dictionary.id] = [
        _settlement(
            fixture.dictionary.id,
            "Атаки",
            modern_settlement_name="Атаки",
            community_name="Хотинська територіальна громада",
            district="Хот.",
        )
    ]
    geo = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text="Атаки",
        role=EntryFieldRole.GEOGRAPHIC_LABEL,
    )
    other = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text="десь інде",
        role=EntryFieldRole.GEOGRAPHIC_LABEL,
    )
    fixture.lexicography_repository.add_field(geo)
    fixture.lexicography_repository.add_field(other)

    changed = fixture.service.resolve_geographic_labels(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    assert [f.id for f in changed] == [geo.id]
    mapping_id = fixture.sources_repository.settlements[fixture.dictionary.id][0].id
    assert geo.settlement_mapping_id == mapping_id
    assert geo.normalized_text == "Атаки"
    assert other.settlement_mapping_id is None


def test_resolve_geographic_labels_skips_already_linked_and_non_geo_fields() -> None:
    fixture = _AnnotationFixture()
    mapping = _settlement(fixture.dictionary.id, "Атаки")
    fixture.sources_repository.settlements[fixture.dictionary.id] = [mapping]
    linked = _field(
        fixture.entry_id,
        fixture.fragment_id,
        source_text="Атаки",
        role=EntryFieldRole.GEOGRAPHIC_LABEL,
    )
    linked.settlement_mapping_id = uuid4()
    meaning = _field(
        fixture.entry_id, fixture.fragment_id, source_text="Атаки"
    )  # role MEANING
    fixture.lexicography_repository.add_field(linked)
    fixture.lexicography_repository.add_field(meaning)

    changed = fixture.service.resolve_geographic_labels(
        fixture.dictionary.id, fixture.entry_id, fixture.owner_id
    )

    assert changed == []
    assert meaning.settlement_mapping_id is None
