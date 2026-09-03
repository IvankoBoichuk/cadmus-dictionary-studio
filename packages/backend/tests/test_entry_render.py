"""Entry -> Markdown rendering: context assembly, the Jinja2 sandbox, and the
``RenderEntryService`` outcomes (BH-148)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cadmus.infrastructure.entry_render import Jinja2EntryPresentationRenderer
from cadmus.lexicography import (
    ArticleSchema,
    DictionaryEntry,
    EntryAccessError,
    EntryField,
    EntryFieldOrigin,
    EntryFieldRole,
    EntryStatus,
    LexicographyUnitOfWork,
    PresentationTemplateError,
    RenderEntryService,
    SchemaGenerationStatus,
    build_entry_presentation_context,
)
from cadmus.sources import DictionaryAccessError, GetDictionaryService

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
DICTIONARY_ID = uuid4()
ENTRY_ID = uuid4()
OWNER_ID = uuid4()
SCHEMA_ID = uuid4()


def _node(
    name: str,
    *,
    role: EntryFieldRole = EntryFieldRole.OTHER,
    type: str = "string",
    repeatable: bool = False,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "role": role.value,
        "type": type,
        "options": [],
        "repeatable": repeatable,
        "required": False,
        "children": children or [],
    }


def _schema(fields: list[dict[str, Any]], formula: str | None = None) -> ArticleSchema:
    return ArticleSchema(
        id=SCHEMA_ID,
        dictionary_id=DICTIONARY_ID,
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={"fields": fields},
        created_at=NOW,
        created_by=OWNER_ID,
        presentation_formula=formula,
    )


def _entry(schema_id: UUID | None = SCHEMA_ID) -> DictionaryEntry:
    return DictionaryEntry(
        id=ENTRY_ID,
        dictionary_id=DICTIONARY_ID,
        lexeme_id=uuid4(),
        headword="кіт",
        status=EntryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        created_by=OWNER_ID,
        updated_by=OWNER_ID,
        schema_id=schema_id,
    )


def _field(
    field_path: str,
    *,
    role: EntryFieldRole = EntryFieldRole.OTHER,
    source_text: str = "",
    normalized_text: str | None = None,
    position: int = 0,
    origin: EntryFieldOrigin = EntryFieldOrigin.MODEL,
) -> EntryField:
    return EntryField(
        id=uuid4(),
        entry_id=ENTRY_ID,
        fragment_id=uuid4(),
        field_path=field_path,
        role=role,
        position=position,
        source_text=source_text,
        normalized_text=normalized_text,
        origin=origin,
        created_at=NOW,
        created_by=OWNER_ID,
        updated_at=NOW,
        updated_by=OWNER_ID,
    )


# --------------------------------------------------------------------------- #
# build_entry_presentation_context
# --------------------------------------------------------------------------- #


def test_headword_only_leaf_node_carries_its_value() -> None:
    schema = _schema([_node("headword", role=EntryFieldRole.HEADWORD)])
    fields = [_field("headword", role=EntryFieldRole.HEADWORD, source_text="кіт")]

    context = build_entry_presentation_context(_entry(), fields, schema)

    assert context["headword"] == "кіт"
    assert context["entry"] == {"headword": "кіт", "status": "draft"}


def test_headword_falls_back_to_entry_when_no_field() -> None:
    context = build_entry_presentation_context(_entry(), [], _schema([]))

    assert context["headword"] == "кіт"


def test_normalized_text_wins_over_source_text() -> None:
    schema = _schema([_node("meaning", role=EntryFieldRole.MEANING)])
    fields = [
        _field(
            "meaning",
            role=EntryFieldRole.MEANING,
            source_text="raw ocr",
            normalized_text="clean value",
        )
    ]

    context = build_entry_presentation_context(_entry(), fields, schema)

    assert context["meaning"] == "clean value"


def test_repeatable_group_with_nested_repeatable_and_scalar_children() -> None:
    schema = _schema(
        [
            _node(
                "senses",
                type="group",
                repeatable=True,
                children=[
                    _node("meaning", role=EntryFieldRole.MEANING),
                    _node("examples", role=EntryFieldRole.EXAMPLE, repeatable=True),
                ],
            )
        ]
    )
    fields = [
        _field("senses[0].meaning", role=EntryFieldRole.MEANING, source_text="тварина"),
        _field(
            "senses[0].examples[0]",
            role=EntryFieldRole.EXAMPLE,
            source_text="чорний кіт",
        ),
        _field(
            "senses[0].examples[1]",
            role=EntryFieldRole.EXAMPLE,
            source_text="кіт нявкає",
        ),
        _field("senses[1].meaning", role=EntryFieldRole.MEANING, source_text="перен."),
    ]

    context = build_entry_presentation_context(_entry(), fields, schema)

    assert [s["meaning"] for s in context["senses"]] == ["тварина", "перен."]
    assert context["senses"][0]["examples"] == ["чорний кіт", "кіт нявкає"]
    assert context["senses"][1]["examples"] == []


def test_repeatable_index_gaps_are_compacted() -> None:
    schema = _schema([_node("syn", role=EntryFieldRole.SYNONYM, repeatable=True)])
    fields = [
        _field("syn[0]", role=EntryFieldRole.SYNONYM, source_text="кицька"),
        _field("syn[2]", role=EntryFieldRole.SYNONYM, source_text="мурка"),
    ]

    context = build_entry_presentation_context(_entry(), fields, schema)

    assert context["syn"] == ["кицька", "мурка"]


def test_rule_tagged_children_surface_as_lists_on_the_instance() -> None:
    schema = _schema(
        [
            _node(
                "senses",
                type="group",
                repeatable=True,
                children=[_node("meaning", role=EntryFieldRole.MEANING)],
            )
        ]
    )
    fields = [
        _field("senses[0].meaning", role=EntryFieldRole.MEANING, source_text="розм."),
        _field(
            "senses[0].meaning.abbreviation",
            role=EntryFieldRole.ABBREVIATION,
            source_text="розм.",
            origin=EntryFieldOrigin.RULE,
        ),
        _field(
            "senses[0].meaning.geographic_label",
            role=EntryFieldRole.GEOGRAPHIC_LABEL,
            source_text="Полтава",
            origin=EntryFieldOrigin.RULE,
        ),
    ]

    context = build_entry_presentation_context(_entry(), fields, schema)

    meaning = context["senses"][0]["meaning"]
    assert meaning.abbreviations == ["розм."]
    assert meaning.geographic_labels == ["Полтава"]


def test_handles_plain_string_status_role_and_origin_from_the_db_mapping() -> None:
    # The imperative SQLAlchemy mapping loads these columns as plain strings,
    # not StrEnum members -- the builder must not assume ``.value``.
    schema = _schema([_node("meaning", role=EntryFieldRole.MEANING)])
    entry = _entry()
    entry.status = "ready_to_review"  # type: ignore[assignment]
    field = _field("meaning", role=EntryFieldRole.MEANING, source_text="x")
    field.role = "meaning"  # type: ignore[assignment]
    field.origin = "model"  # type: ignore[assignment]

    context = build_entry_presentation_context(entry, [field], schema)

    assert context["entry"]["status"] == "ready_to_review"
    assert context["fields"][0]["role"] == "meaning"
    assert context["fields"][0]["origin"] == "model"


def test_malformed_field_path_is_dropped_from_the_tree_but_kept_in_fields() -> None:
    schema = _schema([_node("meaning", role=EntryFieldRole.MEANING)])
    fields = [
        _field("meaning", role=EntryFieldRole.MEANING, source_text="ok"),
        _field("senses[0][1].bad", role=EntryFieldRole.OTHER, source_text="junk"),
    ]

    context = build_entry_presentation_context(_entry(), fields, schema)

    assert context["meaning"] == "ok"
    assert {f["value"] for f in context["fields"]} == {"ok", "junk"}
    assert [f["field_path"] for f in context["fields"]] == [
        "meaning",
        "senses[0][1].bad",
    ]


# --------------------------------------------------------------------------- #
# Jinja2EntryPresentationRenderer
# --------------------------------------------------------------------------- #


@pytest.fixture
def renderer() -> Jinja2EntryPresentationRenderer:
    return Jinja2EntryPresentationRenderer()


def test_renderer_produces_markdown(renderer: Jinja2EntryPresentationRenderer) -> None:
    out = renderer.render(
        "**{{ headword }}** — {{ meaning }}",
        {"headword": "кіт", "meaning": "тварина"},
    )
    assert out == "**кіт** — тварина"


def test_renderer_missing_deep_attr_renders_empty(
    renderer: Jinja2EntryPresentationRenderer,
) -> None:
    assert renderer.render("[{{ a.b.c }}]", {}) == "[]"


def test_renderer_blocks_dunder_escape_without_leaking(
    renderer: Jinja2EntryPresentationRenderer,
) -> None:
    out = renderer.render('{{ "".__class__.__mro__ }}', {})
    assert "type" not in out and "object" not in out


def test_renderer_syntax_error_becomes_domain_error(
    renderer: Jinja2EntryPresentationRenderer,
) -> None:
    with pytest.raises(PresentationTemplateError):
        renderer.render("{% for x in %}", {})


def test_renderer_runtime_error_becomes_domain_error(
    renderer: Jinja2EntryPresentationRenderer,
) -> None:
    with pytest.raises(PresentationTemplateError):
        renderer.render("{{ 1 / 0 }}", {})


# --------------------------------------------------------------------------- #
# RenderEntryService
# --------------------------------------------------------------------------- #


class _Repo:
    def __init__(
        self,
        entry: DictionaryEntry | None,
        schema: ArticleSchema | None,
        fields: list[EntryField],
    ) -> None:
        self._entry = entry
        self._schema = schema
        self._fields = fields

    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None:
        return self._entry if self._entry and self._entry.id == entry_id else None

    def get_article_schema(self, schema_id: UUID) -> ArticleSchema | None:
        return self._schema if self._schema and self._schema.id == schema_id else None

    def list_fields_for_entry(self, entry_id: UUID) -> list[EntryField]:
        return list(self._fields)


class _UnitOfWork:
    def __init__(self, repo: _Repo) -> None:
        self.lexicography = repo

    def __enter__(self) -> _UnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        return None


class _DictionaryPages:
    def get(self, dictionary_id: UUID, actor_id: UUID, **_: Any) -> None:
        if actor_id != OWNER_ID:
            raise DictionaryAccessError(dictionary_id)


def _service(
    entry: DictionaryEntry | None,
    schema: ArticleSchema | None = None,
    fields: list[EntryField] | None = None,
    renderer: Any | None = None,
) -> RenderEntryService:
    repo = _Repo(entry, schema, fields or [])
    return RenderEntryService(
        unit_of_work_factory=cast(  # minimal fake: only the 3 methods used
            Callable[[], LexicographyUnitOfWork], lambda: _UnitOfWork(repo)
        ),
        dictionary_pages=cast(GetDictionaryService, _DictionaryPages()),
        renderer=renderer or Jinja2EntryPresentationRenderer(),
    )


def test_service_renders_markdown() -> None:
    schema = _schema(
        [_node("headword", role=EntryFieldRole.HEADWORD)],
        formula="# {{ headword }}",
    )
    fields = [_field("headword", role=EntryFieldRole.HEADWORD, source_text="кіт")]

    result = _service(_entry(), schema, fields).render(ENTRY_ID, OWNER_ID)

    assert result.markdown == "# кіт"
    assert result.reason is None


def test_service_collapses_punctuation_the_formula_doubled() -> None:
    schema = _schema(
        [
            _node("headword", role=EntryFieldRole.HEADWORD),
            _node("pos", role=EntryFieldRole.PART_OF_SPEECH),
        ],
        formula="{{ headword }}, {{ pos }}. Ужив.: {{ pos }}...",
    )
    fields = [
        _field("headword", role=EntryFieldRole.HEADWORD, source_text="АЛТИЦА"),
        _field("pos", role=EntryFieldRole.PART_OF_SPEECH, source_text="ж.", position=1),
    ]

    result = _service(_entry(), schema, fields).render(ENTRY_ID, OWNER_ID)

    # raw render is "АЛТИЦА, ж.. Ужив.: ж...." -- the doubled period after the
    # abbreviation collapses, the trailing run stays an ellipsis.
    assert result.markdown == "АЛТИЦА, ж. Ужив.: ж..."


def test_service_reports_no_schema_when_entry_has_none() -> None:
    result = _service(_entry(schema_id=None)).render(ENTRY_ID, OWNER_ID)

    assert result.markdown is None
    assert result.reason == "no_schema"


def test_service_reports_no_formula_when_column_blank() -> None:
    schema = _schema([_node("headword")], formula="   ")

    result = _service(_entry(), schema).render(ENTRY_ID, OWNER_ID)

    assert result.reason == "no_formula"


def test_service_reports_template_error_with_message() -> None:
    schema = _schema([_node("headword")], formula="{% for x in %}")

    result = _service(_entry(), schema).render(ENTRY_ID, OWNER_ID)

    assert result.markdown is None
    assert result.reason == "template_error"
    assert result.error


def test_service_raises_entry_access_error_for_foreign_actor() -> None:
    schema = _schema([_node("headword")], formula="{{ headword }}")

    with pytest.raises(EntryAccessError):
        _service(_entry(), schema).render(ENTRY_ID, uuid4())


def test_service_raises_entry_access_error_for_unknown_entry() -> None:
    with pytest.raises(EntryAccessError):
        _service(None).render(ENTRY_ID, OWNER_ID)
