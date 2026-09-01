"""Application-owned ports for lexicography infrastructure."""

from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID

from cadmus.lexicography.domain import (
    ArticleSchema,
    ArticleSchemaGenerationSnapshot,
    DictionaryEntry,
    DictionaryScanSnapshot,
    EntryExtractionSnapshot,
    EntryField,
    EntryFragment,
    EntryStatus,
    ExtractedField,
    GeneratedSchema,
    Lexeme,
    LexemeEvent,
    LexemeStatus,
    OcrSuggestionTaskSnapshot,
)


class LexicographyRepository(Protocol):
    """Persistence operations needed by the lexeme use cases."""

    def add_lexeme(self, lexeme: Lexeme) -> None: ...

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]: ...

    def get_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> Lexeme | None: ...

    def update_lexeme(self, lexeme: Lexeme) -> None: ...

    def delete_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> None: ...

    def add_lexeme_event(self, event: LexemeEvent) -> None: ...

    def list_page_ids_with_lexemes(self, dictionary_id: UUID) -> set[UUID]: ...

    def has_any_lexeme(self, dictionary_id: UUID) -> bool: ...

    def count_lexemes_by_status(
        self, dictionary_id: UUID
    ) -> dict[LexemeStatus, int]: ...

    def count_entries_by_status(
        self, dictionary_id: UUID
    ) -> dict[EntryStatus, int]: ...

    def add_article_schema(self, schema: ArticleSchema) -> None: ...

    def get_article_schema(self, schema_id: UUID) -> ArticleSchema | None: ...

    def get_active_article_schema(
        self, dictionary_id: UUID
    ) -> ArticleSchema | None: ...

    def list_article_schemas(self, dictionary_id: UUID) -> list[ArticleSchema]: ...

    def update_article_schema(self, schema: ArticleSchema) -> None: ...

    def add_entry(self, entry: DictionaryEntry) -> None: ...

    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None: ...

    def get_entry_by_lexeme(self, lexeme_id: UUID) -> DictionaryEntry | None: ...

    def list_entries_for_dictionary(
        self, dictionary_id: UUID
    ) -> list[DictionaryEntry]: ...

    def list_entries_awaiting_review(
        self, dictionary_ids: list[UUID]
    ) -> list[DictionaryEntry]: ...

    def count_fields_by_entry(self, dictionary_id: UUID) -> dict[UUID, int]: ...

    def update_entry(self, entry: DictionaryEntry) -> None: ...

    def add_fragment(self, fragment: EntryFragment) -> None: ...

    def list_fragments_for_entry(self, entry_id: UUID) -> list[EntryFragment]: ...

    def add_field(self, field: EntryField) -> None: ...

    def list_fields_for_entry(self, entry_id: UUID) -> list[EntryField]: ...

    def update_field(self, field: EntryField) -> None: ...

    def delete_field(self, field_id: UUID) -> None: ...


class LexicographyUnitOfWork(Protocol):
    """Transaction boundary controlled by a lexicography use case."""

    @property
    def lexicography(self) -> LexicographyRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type LexicographyUnitOfWorkFactory = Callable[[], LexicographyUnitOfWork]


SUGGEST_LEXEMES_TASK_NAME = "cadmus.lexicography.suggest_lexemes"


class OcrSuggestionQueueUnavailableError(RuntimeError):
    """Raised when the OCR suggestion queue infrastructure cannot be reached."""


class OcrSuggestionQueue(Protocol):
    """Port used to hand off worker-side OCR word suggestion and read it back.

    Ephemeral by design: implementations are expected to hold the result in
    a short-lived store (e.g. the Celery result backend), not Postgres --
    suggestions are candidates, never source evidence, until a user accepts
    one and it becomes a real ``Lexeme`` (see ``CreateLexemeService``).
    """

    def enqueue_suggestions(
        self, source_file_id: UUID, page_id: UUID, language: str
    ) -> str: ...

    def get_suggestions_task(self, task_id: str) -> OcrSuggestionTaskSnapshot: ...


SCAN_DICTIONARY_TASK_NAME = "cadmus.lexicography.scan_dictionary"


class DictionaryScanQueueUnavailableError(RuntimeError):
    """Raised when the whole-dictionary OCR scan queue cannot be reached."""


class DictionaryScanQueue(Protocol):
    """Port used to hand off a whole-dictionary OCR scan and read it back.

    Unlike ``OcrSuggestionQueue`` (one page, suggestions only), the worker
    task behind this port creates draft ``Lexeme`` rows itself as it walks
    every unscanned page -- this port only reports progress, never
    suggestions.
    """

    def enqueue_scan(self, dictionary_id: UUID, actor_id: UUID) -> str: ...

    def get_scan_task(self, task_id: str) -> DictionaryScanSnapshot: ...


GENERATE_ARTICLE_SCHEMA_TASK_NAME = "cadmus.lexicography.generate_article_schema"


class ArticleSchemaQueueUnavailableError(RuntimeError):
    """Raised when the article schema generation queue cannot be reached."""


class ArticleSchemaQueue(Protocol):
    """Port used to hand off a whole-dictionary article schema generation.

    The worker task behind this port persists the resulting
    ``ArticleSchema`` version itself -- this port only reports progress.
    """

    def enqueue_generation(self, dictionary_id: UUID, actor_id: UUID) -> str: ...

    def get_generation_task(self, task_id: str) -> ArticleSchemaGenerationSnapshot: ...


EXTRACT_ENTRY_FIELDS_TASK_NAME = "cadmus.lexicography.extract_entry_fields"


class EntryExtractionQueueUnavailableError(RuntimeError):
    """Raised when the entry field extraction queue cannot be reached."""


class EntryExtractionQueue(Protocol):
    """Port used to hand off a single entry's field extraction."""

    def enqueue_extraction(self, entry_id: UUID, actor_id: UUID) -> str: ...

    def get_extraction_task(self, task_id: str) -> EntryExtractionSnapshot: ...


class AiSchemaProvider(Protocol):
    """Worker-side port to an AI provider that turns a dictionary's free-text
    ``article_description`` into a structured schema, and extracts fields from
    one entry fragment's plain ``recognized_text`` per that schema (BH-148).

    Mirrors the canonical provider-neutral contract shape documented in
    ``docs/architecture.md`` §8 (``OcrProvider``): domain/application code
    depends only on this ``Protocol``, never on a concrete AI SDK.
    """

    def generate_schema(self, article_description: str) -> GeneratedSchema: ...

    def extract_fields(
        self, schema: ArticleSchema, text: str
    ) -> list[ExtractedField]: ...


class EntryPresentationRenderer(Protocol):
    """Worker/API-side port that renders an entry's assembled context through
    an ``ArticleSchema.presentation_formula`` (a Jinja2 template) into Markdown.

    Kept behind a ``Protocol`` for the same reason as ``AiSchemaProvider``: the
    Jinja2 engine and its sandbox are an infrastructure concern, so domain and
    application code depend only on this contract. Implementations raise
    ``cadmus.lexicography.domain.PresentationTemplateError`` on a bad template.
    """

    def render(self, template_source: str, context: Mapping[str, Any]) -> str: ...
