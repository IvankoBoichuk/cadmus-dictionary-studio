"""Use cases for manually validated links to external reference lemmas."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.access import Permission
from cadmus.lexicography.domain import DictionaryEntry, EntryAccessError
from cadmus.lexicography.ports import LexicographyUnitOfWorkFactory
from cadmus.lexicography.reference_link_domain import (
    EntryReferenceLink,
    ReferenceLinkOrigin,
    ReferenceLinkStatus,
    ReferenceRelationType,
)
from cadmus.lexicography.reference_link_ports import EntryReferenceLinkUnitOfWorkFactory
from cadmus.reference_lexicon import ReferenceLemma, ReferenceLexiconQueryService
from cadmus.sources import DictionaryAccessError
from cadmus.sources.application import GetDictionaryService


class ReferenceLinkAccessError(LookupError):
    """Raised when a link is missing or does not belong to the requested entry."""


class ReferenceLemmaNotStandardError(ValueError):
    """Raised when a non-standard lemma is selected as a standard equivalent."""


@dataclass(frozen=True)
class LinkedReferenceLemma:
    """An entry link paired with its currently active reference lemma."""

    link: EntryReferenceLink
    lemma: ReferenceLemma


class ManageEntryReferenceLinksService:
    """Authorize, create, list and delete manually confirmed lexical mappings."""

    def __init__(
        self,
        *,
        lexicography_unit_of_work_factory: LexicographyUnitOfWorkFactory,
        reference_link_unit_of_work_factory: (EntryReferenceLinkUnitOfWorkFactory),
        dictionary_pages: GetDictionaryService,
        reference_lexicon: ReferenceLexiconQueryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._lexicography_unit_of_work_factory = lexicography_unit_of_work_factory
        self._reference_link_unit_of_work_factory = reference_link_unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._reference_lexicon = reference_lexicon
        self._clock = clock

    def _authorize(
        self,
        entry_id: UUID,
        actor_id: UUID,
        permission: Permission,
    ) -> DictionaryEntry:
        with self._lexicography_unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
        if entry is None:
            raise EntryAccessError(entry_id)
        try:
            self._dictionary_pages.get(
                entry.dictionary_id,
                actor_id,
                required_permission=permission,
            )
        except DictionaryAccessError as error:
            raise EntryAccessError(entry_id) from error
        return entry

    def list(self, entry_id: UUID, actor_id: UUID) -> list[LinkedReferenceLemma]:
        self._authorize(entry_id, actor_id, Permission.VIEW)
        with self._reference_link_unit_of_work_factory() as unit_of_work:
            links = unit_of_work.reference_links.list_for_entry(entry_id)

        result: list[LinkedReferenceLemma] = []
        for link in links:
            lemma = self._reference_lexicon.get_lemma(link.reference_lemma_id)
            result.append(LinkedReferenceLemma(link=link, lemma=lemma))
        return result

    def create(
        self,
        entry_id: UUID,
        actor_id: UUID,
        reference_lemma_id: UUID,
        *,
        relation_type: ReferenceRelationType = (
            ReferenceRelationType.STANDARD_EQUIVALENT
        ),
    ) -> LinkedReferenceLemma:
        self._authorize(entry_id, actor_id, Permission.EDIT)
        lemma = self._reference_lexicon.get_lemma(reference_lemma_id)
        if (
            relation_type is ReferenceRelationType.STANDARD_EQUIVALENT
            and not lemma.is_standard
        ):
            raise ReferenceLemmaNotStandardError(str(reference_lemma_id))

        with self._reference_link_unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.reference_links.find(
                entry_id, reference_lemma_id, relation_type
            )
            if existing is not None:
                return LinkedReferenceLemma(link=existing, lemma=lemma)

            link = EntryReferenceLink(
                id=uuid4(),
                entry_id=entry_id,
                reference_lemma_id=reference_lemma_id,
                relation_type=relation_type,
                origin=ReferenceLinkOrigin.MANUAL,
                validation_status=ReferenceLinkStatus.CONFIRMED,
                confidence=None,
                created_at=self._clock(),
                created_by=actor_id,
            )
            unit_of_work.reference_links.add(link)
            unit_of_work.commit()
        return LinkedReferenceLemma(link=link, lemma=lemma)

    def delete(self, entry_id: UUID, link_id: UUID, actor_id: UUID) -> None:
        self._authorize(entry_id, actor_id, Permission.EDIT)
        with self._reference_link_unit_of_work_factory() as unit_of_work:
            link = unit_of_work.reference_links.get(entry_id, link_id)
            if link is None:
                raise ReferenceLinkAccessError(str(link_id))
            unit_of_work.reference_links.delete(entry_id, link_id)
            unit_of_work.commit()
