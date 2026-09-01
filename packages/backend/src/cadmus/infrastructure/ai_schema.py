"""AI-backed article-schema generation and entry field extraction (BH-148).

Worker-only boundary, mirroring ``infrastructure/ocr.py``: calls the
Anthropic API and hands generation/extraction jobs to Celery. Domain and
application code never import this module directly (see
``packages/backend/AGENTS.md``: "Domain code must not import ... OCR SDKs" --
the same rule applies to any external AI provider SDK).
"""

import json
from collections.abc import Sequence
from typing import Any, Final, cast
from uuid import UUID

import anthropic
from celery import Celery, states
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from cadmus.lexicography.domain import (
    SCHEMA_FIELD_TYPES,
    ArticleSchema,
    ArticleSchemaGenerationSnapshot,
    EntryExtractionSnapshot,
    EntryFieldRole,
    ExtractedField,
    FragmentSegment,
    GeneratedSchema,
    OcrSuggestionStatus,
)
from cadmus.lexicography.ports import (
    EXTRACT_ENTRY_FIELDS_TASK_NAME,
    GENERATE_ARTICLE_SCHEMA_TASK_NAME,
    ArticleSchemaQueueUnavailableError,
    EntryExtractionQueueUnavailableError,
)

_QUEUE_ERRORS: Final = (OperationalError, RedisError, OSError)

_LEAF_NODE_PROPERTIES: dict[str, Any] = {
    "name": {"type": "string"},
    "role": {"type": "string", "enum": [role.value for role in EntryFieldRole]},
    "type": {
        "type": "string",
        "enum": list(SCHEMA_FIELD_TYPES),
    },
    "options": {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Allowed string values when type is 'enum'; an empty array for "
            "every other type (including 'abbreviation' and "
            "'geographic_label')."
        ),
    },
    "repeatable": {"type": "boolean"},
    "required": {"type": "boolean"},
}
_LEAF_NODE_REQUIRED = ["name", "role", "type", "options", "repeatable", "required"]
_LEAF_NODE: dict[str, Any] = {
    "type": "object",
    "properties": _LEAF_NODE_PROPERTIES,
    "required": _LEAF_NODE_REQUIRED,
    "additionalProperties": False,
}
_MID_NODE: dict[str, Any] = {
    "type": "object",
    "properties": {
        **_LEAF_NODE_PROPERTIES,
        "children": {"type": "array", "items": _LEAF_NODE},
    },
    "required": [*_LEAF_NODE_REQUIRED, "children"],
    "additionalProperties": False,
}
_TOP_NODE: dict[str, Any] = {
    "type": "object",
    "properties": {
        **_LEAF_NODE_PROPERTIES,
        "children": {"type": "array", "items": _MID_NODE},
    },
    "required": [*_LEAF_NODE_REQUIRED, "children"],
    "additionalProperties": False,
}
"""Three levels of nesting (top field / mid child / leaf grandchild) --
enough for a typical article structure (e.g. ``senses`` -> ``examples`` /
``synonyms``) without the ``$ref`` recursion risk of an unbounded tree under
strict tool-use validation.
"""

_GENERATE_SCHEMA_TOOL_NAME = "propose_article_schema"
_GENERATE_SCHEMA_TOOL: dict[str, Any] = {
    "name": _GENERATE_SCHEMA_TOOL_NAME,
    "description": (
        "Propose a structured field schema for a dictionary article, "
        "derived strictly from the editor's free-text description of the "
        "article's structure. Use role 'other' for anything that doesn't "
        "fit the standard roles. Field 'type' is 'string' for free text, "
        "'number' for numeric values, 'boolean' for yes/no flags, 'date' "
        "for calendar dates, 'enum' for a closed set of values (list them "
        "in 'options'), 'list' for a repeated simple value, 'group' for "
        "a node with child fields, 'abbreviation' for a value the editor "
        "picks from the dictionary's abbreviation list, or "
        "'geographic_label' for one from its settlement list. 'options' "
        "must be an empty array unless 'type' is 'enum'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"fields": {"type": "array", "items": _TOP_NODE}},
        "required": ["fields"],
        "additionalProperties": False,
    },
    "strict": True,
}

_EXTRACTED_FIELD_ITEM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "field_path": {"type": "string"},
        "role": {"type": "string", "enum": [role.value for role in EntryFieldRole]},
        "value": {"type": "string"},
        "segment_start": {"type": "integer"},
        "segment_end": {"type": "integer"},
        "confidence": {"type": "number"},
    },
    "required": [
        "field_path",
        "role",
        "value",
        "segment_start",
        "segment_end",
        "confidence",
    ],
    "additionalProperties": False,
}
_EXTRACT_FIELDS_TOOL_NAME = "extract_entry_fields"
_EXTRACT_FIELDS_TOOL: dict[str, Any] = {
    "name": _EXTRACT_FIELDS_TOOL_NAME,
    "description": (
        "Extract structured fields from one dictionary entry, per the "
        "given article schema. The entry's text is given as a numbered "
        "list of OCR-recognized word segments (BH-148 ALTO segmentation, "
        "experimental). segment_start/segment_end must be the 0-based "
        "indices of the first and last segment that make up one field's "
        "value -- an inclusive, contiguous range into the exact segment "
        "list given, never a character offset or a paraphrase."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"fields": {"type": "array", "items": _EXTRACTED_FIELD_ITEM}},
        "required": ["fields"],
        "additionalProperties": False,
    },
    "strict": True,
}


class AiSchemaProviderError(RuntimeError):
    """Raised when the AI schema provider fails, times out, or its output
    cannot be parsed into the expected shape."""


def _first_tool_use(response: "anthropic.types.Message", tool_name: str) -> Any:
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block
    raise AiSchemaProviderError(f"model did not call the {tool_name!r} tool")


class AnthropicAiSchemaProvider:
    """Calls Claude to propose an article schema and to extract fields from
    one entry fragment's text per that schema (BH-148)."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)
        self._model = model

    def generate_schema(self, article_description: str) -> GeneratedSchema:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8000,
                output_config=cast(Any, {"effort": "medium"}),
                tools=cast(Any, [_GENERATE_SCHEMA_TOOL]),
                tool_choice=cast(
                    Any, {"type": "tool", "name": _GENERATE_SCHEMA_TOOL_NAME}
                ),
                messages=cast(
                    Any,
                    [
                        {
                            "role": "user",
                            "content": (
                                "Propose a structured field schema for a "
                                "dictionary article based on this description "
                                "of its structure:\n\n" + article_description
                            ),
                        }
                    ],
                ),
            )
        except (anthropic.APIError, anthropic.APIConnectionError) as error:
            raise AiSchemaProviderError(f"schema generation failed: {error}") from error

        tool_use = _first_tool_use(response, _GENERATE_SCHEMA_TOOL_NAME)
        definition = tool_use.input
        if not isinstance(definition, dict) or "fields" not in definition:
            raise AiSchemaProviderError("schema generation returned malformed output")
        return GeneratedSchema(
            definition=definition,
            raw_response=response.model_dump(mode="json"),
            provider_name=f"anthropic:{self._model}",
        )

    def extract_fields(
        self, schema: ArticleSchema, segments: Sequence[FragmentSegment]
    ) -> list[ExtractedField]:
        segment_count = len(segments)
        numbered_segments = "\n".join(
            f"[{segment.index}] {segment.text}" for segment in segments
        )
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8000,
                output_config=cast(Any, {"effort": "medium"}),
                tools=cast(Any, [_EXTRACT_FIELDS_TOOL]),
                tool_choice=cast(
                    Any, {"type": "tool", "name": _EXTRACT_FIELDS_TOOL_NAME}
                ),
                messages=cast(
                    Any,
                    [
                        {
                            "role": "user",
                            "content": (
                                "Extract structured fields from this "
                                "dictionary entry, per the given schema.\n\n"
                                f"Schema:\n{json.dumps(schema.definition)}\n\n"
                                "OCR word segments, one per line as "
                                '"[index] word", in reading order:\n'
                                f"{numbered_segments}"
                            ),
                        }
                    ],
                ),
            )
        except (anthropic.APIError, anthropic.APIConnectionError) as error:
            raise AiSchemaProviderError(f"field extraction failed: {error}") from error

        tool_use = _first_tool_use(response, _EXTRACT_FIELDS_TOOL_NAME)
        payload = tool_use.input
        if not isinstance(payload, dict) or "fields" not in payload:
            raise AiSchemaProviderError("field extraction returned malformed output")

        extracted: list[ExtractedField] = []
        for item in payload["fields"]:
            try:
                segment_start = int(item["segment_start"])
                segment_end = int(item["segment_end"])
                if not (0 <= segment_start <= segment_end < segment_count):
                    raise AiSchemaProviderError(
                        "field extraction returned an out-of-range segment span: "
                        f"{segment_start}..{segment_end} (have {segment_count} "
                        "segments)"
                    )
                extracted.append(
                    ExtractedField(
                        field_path=str(item["field_path"]),
                        role=EntryFieldRole(item["role"]),
                        value=str(item["value"]),
                        segment_start=segment_start,
                        segment_end=segment_end,
                        confidence=float(item["confidence"]),
                    )
                )
            except (KeyError, ValueError, TypeError) as error:
                raise AiSchemaProviderError(
                    f"field extraction returned a malformed field: {error}"
                ) from error
        return extracted


class CeleryArticleSchemaQueue:
    """Hand article-schema generation jobs to the worker through Celery.

    The worker task persists the resulting ``ArticleSchema`` itself; the
    Celery result only reports which version was created, or the failure
    reason -- mirrors ``CeleryOcrSuggestionQueue``.
    """

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_generation(self, dictionary_id: UUID, actor_id: UUID) -> str:
        try:
            result = self._celery_app.send_task(
                GENERATE_ARTICLE_SCHEMA_TASK_NAME,
                args=[str(dictionary_id), str(actor_id)],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise ArticleSchemaQueueUnavailableError(
                "article schema generation queue is unavailable"
            ) from error
        return str(result.id)

    def get_generation_task(self, task_id: str) -> ArticleSchemaGenerationSnapshot:
        try:
            result = self._celery_app.AsyncResult(task_id)
            state = result.state
            value = result.result if state == states.SUCCESS else None
        except _QUEUE_ERRORS as error:
            raise ArticleSchemaQueueUnavailableError(
                "article schema generation queue is unavailable"
            ) from error

        if state == states.SUCCESS:
            payload = value if isinstance(value, dict) else {}
            if payload.get("status") == "failed":
                return ArticleSchemaGenerationSnapshot(
                    task_id=task_id,
                    status=OcrSuggestionStatus.FAILED,
                    error=str(payload.get("error", "schema generation task failed")),
                )
            schema_id = payload.get("schema_id")
            return ArticleSchemaGenerationSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.SUCCEEDED,
                schema_id=UUID(schema_id) if schema_id else None,
            )
        if state in {states.FAILURE, states.REVOKED}:
            return ArticleSchemaGenerationSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.FAILED,
                error="schema generation task failed",
            )
        if state in {states.STARTED, states.RETRY}:
            return ArticleSchemaGenerationSnapshot(
                task_id=task_id, status=OcrSuggestionStatus.RUNNING
            )
        return ArticleSchemaGenerationSnapshot(
            task_id=task_id, status=OcrSuggestionStatus.QUEUED
        )


class CeleryEntryExtractionQueue:
    """Hand entry field-extraction jobs to the worker through Celery.

    The worker task persists each extracted ``EntryField`` itself
    (``origin=EntryFieldOrigin.MODEL``) and runs the rule-based
    abbreviation/geography pass -- the Celery result only reports how many
    fields were created, or the failure reason.
    """

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_extraction(self, entry_id: UUID, actor_id: UUID) -> str:
        try:
            result = self._celery_app.send_task(
                EXTRACT_ENTRY_FIELDS_TASK_NAME,
                args=[str(entry_id), str(actor_id)],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise EntryExtractionQueueUnavailableError(
                "entry field extraction queue is unavailable"
            ) from error
        return str(result.id)

    def get_extraction_task(self, task_id: str) -> EntryExtractionSnapshot:
        try:
            result = self._celery_app.AsyncResult(task_id)
            state = result.state
            value = result.result if state == states.SUCCESS else None
        except _QUEUE_ERRORS as error:
            raise EntryExtractionQueueUnavailableError(
                "entry field extraction queue is unavailable"
            ) from error

        if state == states.SUCCESS:
            payload = value if isinstance(value, dict) else {}
            if payload.get("status") == "failed":
                return EntryExtractionSnapshot(
                    task_id=task_id,
                    status=OcrSuggestionStatus.FAILED,
                    error=str(payload.get("error", "field extraction task failed")),
                )
            return EntryExtractionSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.SUCCEEDED,
                created_fields=int(payload.get("created_fields", 0)),
            )
        if state in {states.FAILURE, states.REVOKED}:
            return EntryExtractionSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.FAILED,
                error="field extraction task failed",
            )
        if state in {states.STARTED, states.RETRY}:
            return EntryExtractionSnapshot(
                task_id=task_id, status=OcrSuggestionStatus.RUNNING
            )
        return EntryExtractionSnapshot(
            task_id=task_id, status=OcrSuggestionStatus.QUEUED
        )
