"""Lexicography application contracts: manually selected lexemes (BH-54)."""

from cadmus.lexicography.application import (
    CreateLexemeService,
    LexemeInput,
    LexemeQueryService,
)
from cadmus.lexicography.domain import (
    DUPLICATE_OVERLAP_RATIO,
    MAX_SOURCE_TEXT_LENGTH,
    DuplicateLexemeError,
    Lexeme,
    LexemeAccessError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeValidationError,
    find_overlapping_lexeme,
    validate_lexeme_fields,
)
from cadmus.lexicography.ports import (
    LexicographyRepository,
    LexicographyUnitOfWork,
    LexicographyUnitOfWorkFactory,
)

__all__ = [
    "DUPLICATE_OVERLAP_RATIO",
    "MAX_SOURCE_TEXT_LENGTH",
    "CreateLexemeService",
    "DuplicateLexemeError",
    "Lexeme",
    "LexemeAccessError",
    "LexemeInput",
    "LexemeOrigin",
    "LexemePageNotFoundError",
    "LexemeQueryService",
    "LexemeValidationError",
    "LexicographyRepository",
    "LexicographyUnitOfWork",
    "LexicographyUnitOfWorkFactory",
    "find_overlapping_lexeme",
    "validate_lexeme_fields",
]
