"""SQLAlchemy persistence for entry to reference-lemma mappings."""

from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    delete,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

import cadmus.infrastructure.lexicography  # noqa: F401
import cadmus.infrastructure.reference_lexicon  # noqa: F401
from cadmus.infrastructure.database import metadata
from cadmus.lexicography.reference_link_domain import (
    EntryReferenceLink,
    ReferenceLinkOrigin,
    ReferenceLinkStatus,
    ReferenceRelationType,
)
from cadmus.lexicography.reference_link_ports import EntryReferenceLinkUnitOfWorkFactory

reference_link_registry = registry(metadata=metadata)

entry_reference_links = Table(
    "entry_reference_links",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "entry_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionary_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "reference_lemma_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.reference_lemmas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("relation_type", String(32), nullable=False),
    Column("origin", String(16), nullable=False),
    Column("validation_status", String(16), nullable=False),
    Column("confidence", Float, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    UniqueConstraint(
        "entry_id",
        "reference_lemma_id",
        "relation_type",
        name="uq_entry_reference_links_entry_lemma_relation",
    ),
    CheckConstraint(
        "relation_type IN "
        "('standard_equivalent', 'synonym', 'approximate_equivalent', 'hypernym', 'related')",
        name="entry_reference_link_relation_type",
    ),
    CheckConstraint("origin IN ('manual')", name="entry_reference_link_origin"),
    CheckConstraint(
        "validation_status IN ('confirmed')",
        name="entry_reference_link_validation_status",
    ),
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
        name="entry_reference_link_confidence",
    ),
)

reference_link_registry.map_imperatively(EntryReferenceLink, entry_reference_links)


class SqlAlchemyEntryReferenceLinkRepository:
    """Entry-reference-link repository backed by a caller-owned session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, link: EntryReferenceLink) -> None:
        self._session.add(link)

    def list_for_entry(self, entry_id: UUID) -> list[EntryReferenceLink]:
        return list(
            self._session.scalars(
                select(EntryReferenceLink)
                .where(entry_reference_links.c.entry_id == entry_id)
                .order_by(entry_reference_links.c.created_at, entry_reference_links.c.id)
            )
        )

    def get(self, entry_id: UUID, link_id: UUID) -> EntryReferenceLink | None:
        return self._session.scalar(
            select(EntryReferenceLink).where(
                entry_reference_links.c.id == link_id,
                entry_reference_links.c.entry_id == entry_id,
            )
        )

    def find(
        self,
        entry_id: UUID,
        reference_lemma_id: UUID,
        relation_type: ReferenceRelationType,
    ) -> EntryReferenceLink | None:
        return self._session.scalar(
            select(EntryReferenceLink).where(
                entry_reference_links.c.entry_id == entry_id,
                entry_reference_links.c.reference_lemma_id == reference_lemma_id,
                entry_reference_links.c.relation_type == relation_type.value,
            )
        )

    def delete(self, entry_id: UUID, link_id: UUID) -> None:
        self._session.execute(
            delete(entry_reference_links).where(
                entry_reference_links.c.id == link_id,
                entry_reference_links.c.entry_id == entry_id,
            )
        )


class SqlAlchemyEntryReferenceLinkUnitOfWork:
    """Session-backed reference-link transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.reference_links: SqlAlchemyEntryReferenceLinkRepository

    def __enter__(self) -> "SqlAlchemyEntryReferenceLinkUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.reference_links = SqlAlchemyEntryReferenceLinkRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("reference-link unit of work has not been entered")
        self._session.commit()


def create_entry_reference_link_unit_of_work_factory(
    engine: Engine,
) -> EntryReferenceLinkUnitOfWorkFactory:
    """Build one fresh reference-link transaction per use case."""

    return lambda: SqlAlchemyEntryReferenceLinkUnitOfWork(engine)
