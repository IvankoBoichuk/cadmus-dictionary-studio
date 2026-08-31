"""Domain model for explicit links from Cadmus entries to reference lemmas."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ReferenceRelationType(StrEnum):
    """Semantic relationship asserted between a dictionary entry and a lemma."""

    STANDARD_EQUIVALENT = "standard_equivalent"
    SYNONYM = "synonym"
    APPROXIMATE_EQUIVALENT = "approximate_equivalent"
    HYPERNYM = "hypernym"
    RELATED = "related"


class ReferenceLinkOrigin(StrEnum):
    """How a link entered Cadmus."""

    MANUAL = "manual"


class ReferenceLinkStatus(StrEnum):
    """Human-validation state of a reference link."""

    CONFIRMED = "confirmed"


@dataclass
class EntryReferenceLink:
    """A validated semantic link that never mutates the source dictionary text."""

    id: UUID
    entry_id: UUID
    reference_lemma_id: UUID
    relation_type: ReferenceRelationType
    origin: ReferenceLinkOrigin
    validation_status: ReferenceLinkStatus
    created_at: datetime
    created_by: UUID
    confidence: float | None = None
