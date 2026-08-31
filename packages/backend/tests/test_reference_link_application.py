"""Application-service tests for manually confirmed reference links."""

from contextlib import AbstractContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    DictionaryEntry,
    EntryStatus,
    ManageEntryReferenceLinksService,
    ReferenceLemmaNotStandardError,
    ReferenceRelationType,
)
from cadmus.lexicography.ports import (
    LexicographyUnitOfWork,
)
from cadmus.lexicography.reference_link_ports import (
    EntryReferenceLinkUnitOfWorkFactory,
)
from cadmus.reference_lexicon import ReferenceLemma, ReferenceLexiconQueryService
from cadmus.sources import GetDictionaryService

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
ENTRY_ID = uuid4()
DICTIONARY_ID = uuid4()
ACTOR_ID = uuid4()
LEMMA_ID = uuid4()


class _LexicographyRepositoryStub:
    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None:
        assert entry_id == ENTRY_ID
        return DictionaryEntry(
            id=ENTRY_ID,
            dictionary_id=DICTIONARY_ID,
            lexeme_id=uuid4(),
            headword="ґазда",
            status=EntryStatus.DRAFT,
            created_at=NOW,
            updated_at=NOW,
            created_by=ACTOR_ID,
            updated_by=ACTOR_ID,
        )


class _LexicographyUnitOfWorkStub(
    AbstractContextManager["_LexicographyUnitOfWorkStub"]
):
    def __init__(self) -> None:
        self.lexicography = _LexicographyRepositoryStub()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        raise AssertionError("read-only authorization must not commit")


class _DictionaryServiceStub:
    def get(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        *,
        required_permission: object,
    ) -> object:
        assert dictionary_id == DICTIONARY_ID
        assert actor_id == ACTOR_ID
        assert required_permission is not None
        return object()


class _ReferenceLexiconQueryStub:
    def get_lemma(self, lemma_id: UUID) -> ReferenceLemma:
        assert lemma_id == LEMMA_ID
        return ReferenceLemma(
            id=LEMMA_ID,
            lexicon_id=uuid4(),
            external_key="газда|noun|anim,m",
            lemma="газда",
            normalized_lemma="газда",
            part_of_speech="noun",
            key_tags=["anim", "m"],
            is_standard=False,
        )


def test_standard_equivalent_rejects_non_standard_reference_before_write() -> None:
    def lexicography_factory() -> LexicographyUnitOfWork:
        return cast(LexicographyUnitOfWork, _LexicographyUnitOfWorkStub())

    link_factory = cast(
        EntryReferenceLinkUnitOfWorkFactory,
        lambda: (_ for _ in ()).throw(
            AssertionError("non-standard reference must be rejected before persistence")
        ),
    )
    service = ManageEntryReferenceLinksService(
        lexicography_unit_of_work_factory=lexicography_factory,
        reference_link_unit_of_work_factory=link_factory,
        dictionary_pages=cast(GetDictionaryService, _DictionaryServiceStub()),
        reference_lexicon=cast(
            ReferenceLexiconQueryService,
            _ReferenceLexiconQueryStub(),
        ),
    )

    with pytest.raises(ReferenceLemmaNotStandardError):
        service.create(
            ENTRY_ID,
            ACTOR_ID,
            LEMMA_ID,
            relation_type=ReferenceRelationType.STANDARD_EQUIVALENT,
        )
