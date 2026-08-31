"""SQLAlchemy persistence for versioned external lexical reference data."""

from collections.abc import Sequence
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    case,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.reference_lexicon.domain import (
    MorphologyFeatures,
    ReferenceLemma,
    ReferenceLemmaMatch,
    ReferenceLexicon,
    ReferenceMatchType,
    ReferenceWordForm,
    VesumRecord,
)
from cadmus.reference_lexicon.ports import ReferenceLexiconUnitOfWorkFactory

reference_lexicon_registry = registry(metadata=metadata)

reference_lexicons = Table(
    "reference_lexicons",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("code", String(64), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column("language_code", String(16), nullable=False),
    Column("version", String(64), nullable=False),
    Column("source_url", String(500), nullable=False),
    Column("license_id", String(64), nullable=False),
    Column("source_commit", String(64), nullable=True),
    Column("checksum", String(128), nullable=False),
    Column("imported_at", DateTime(timezone=True), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
)

reference_lemmas = Table(
    "reference_lemmas",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "lexicon_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.reference_lexicons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("external_key", String(700), nullable=False),
    Column("lemma", String(500), nullable=False),
    Column("normalized_lemma", String(500), nullable=False, index=True),
    Column("part_of_speech", String(32), nullable=False),
    Column("key_tags", JSONB, nullable=False),
    Column("is_standard", Boolean, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    UniqueConstraint(
        "lexicon_id", "external_key", name="uq_reference_lemmas_lexicon_external_key"
    ),
)

reference_word_forms = Table(
    "reference_word_forms",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "lemma_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.reference_lemmas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("form", String(500), nullable=False),
    Column("normalized_form", String(500), nullable=False, index=True),
    Column("morphology", Text, nullable=False),
    Column("morphology_tags", JSONB, nullable=False),
    Column("morphology_features", JSONB, nullable=False),
    Column("is_standard", Boolean, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
)

reference_lexicon_registry.map_imperatively(ReferenceLexicon, reference_lexicons)
reference_lexicon_registry.map_imperatively(ReferenceLemma, reference_lemmas)
reference_lexicon_registry.map_imperatively(ReferenceWordForm, reference_word_forms)


class SqlAlchemyReferenceLexiconRepository:
    """Reference-lexicon repository backed by a caller-owned session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_lexicon_by_code(self, code: str) -> ReferenceLexicon | None:
        return self._session.scalar(
            select(ReferenceLexicon).where(reference_lexicons.c.code == code)
        )

    def get_lemma(self, lemma_id: UUID) -> ReferenceLemma | None:
        return self._session.get(ReferenceLemma, lemma_id)

    def search_lemmas(
        self,
        *,
        lexicon_id: UUID,
        query: str,
        standard_only: bool,
        limit: int,
    ) -> list[ReferenceLemmaMatch]:
        predicates = [
            reference_lemmas.c.lexicon_id == lexicon_id,
            reference_lemmas.c.is_active.is_(True),
        ]
        if standard_only:
            predicates.append(reference_lemmas.c.is_standard.is_(True))

        direct_stmt = (
            select(ReferenceLemma)
            .where(
                *predicates,
                reference_lemmas.c.normalized_lemma.startswith(query),
            )
            .order_by(
                case(
                    (reference_lemmas.c.normalized_lemma == query, 0),
                    else_=1,
                ),
                reference_lemmas.c.normalized_lemma,
                reference_lemmas.c.part_of_speech,
            )
            .limit(limit)
        )
        direct = list(self._session.scalars(direct_stmt))
        results = [
            ReferenceLemmaMatch(lemma=lemma, match_type=ReferenceMatchType.LEMMA)
            for lemma in direct
        ]
        seen = {lemma.id for lemma in direct}
        if len(results) >= limit:
            return results

        form_predicates = [
            reference_word_forms.c.is_active.is_(True),
            reference_word_forms.c.normalized_form.startswith(query),
        ]
        if standard_only:
            form_predicates.append(reference_word_forms.c.is_standard.is_(True))

        form_stmt = (
            select(
                ReferenceLemma,
                reference_word_forms.c.form,
                reference_word_forms.c.morphology,
                reference_word_forms.c.morphology_tags,
                reference_word_forms.c.morphology_features,
            )
            .join(
                reference_word_forms,
                reference_word_forms.c.lemma_id == reference_lemmas.c.id,
            )
            .where(*predicates, *form_predicates)
            .order_by(
                case(
                    (reference_word_forms.c.normalized_form == query, 0),
                    else_=1,
                ),
                reference_word_forms.c.normalized_form,
                reference_lemmas.c.normalized_lemma,
            )
            .limit(limit * 4)
        )
        for row in self._session.execute(form_stmt):
            lemma = row[0]
            if lemma.id in seen:
                continue
            seen.add(lemma.id)
            results.append(
                ReferenceLemmaMatch(
                    lemma=lemma,
                    match_type=ReferenceMatchType.WORD_FORM,
                    matched_form=str(row[1]),
                    matched_form_morphology=str(row[2]),
                    matched_form_tags=cast(list[str], row[3]),
                    matched_form_features=cast(MorphologyFeatures, row[4]),
                )
            )
            if len(results) >= limit:
                break
        return results

    def upsert_lexicon(self, lexicon: ReferenceLexicon) -> None:
        statement = insert(reference_lexicons).values(
            id=lexicon.id,
            code=lexicon.code,
            name=lexicon.name,
            language_code=lexicon.language_code,
            version=lexicon.version,
            source_url=lexicon.source_url,
            license_id=lexicon.license_id,
            source_commit=lexicon.source_commit,
            checksum=lexicon.checksum,
            imported_at=lexicon.imported_at,
            is_active=lexicon.is_active,
        )
        self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[reference_lexicons.c.code],
                set_={
                    "name": statement.excluded.name,
                    "language_code": statement.excluded.language_code,
                    "version": statement.excluded.version,
                    "source_url": statement.excluded.source_url,
                    "license_id": statement.excluded.license_id,
                    "source_commit": statement.excluded.source_commit,
                    "checksum": statement.excluded.checksum,
                    "imported_at": statement.excluded.imported_at,
                    "is_active": True,
                },
            )
        )

    def deactivate_content(self, lexicon_id: UUID) -> None:
        lemma_ids = select(reference_lemmas.c.id).where(
            reference_lemmas.c.lexicon_id == lexicon_id
        )
        self._session.execute(
            update(reference_word_forms)
            .where(reference_word_forms.c.lemma_id.in_(lemma_ids))
            .values(is_active=False)
        )
        self._session.execute(
            update(reference_lemmas)
            .where(reference_lemmas.c.lexicon_id == lexicon_id)
            .values(is_active=False, is_standard=False)
        )

    def upsert_records(self, records: Sequence[VesumRecord]) -> None:
        if not records:
            return

        lemma_rows: dict[UUID, dict[str, object]] = {}
        form_rows: dict[UUID, dict[str, object]] = {}
        for record in records:
            lemma = record.lemma
            row = lemma_rows.get(lemma.id)
            if row is None:
                lemma_rows[lemma.id] = {
                    "id": lemma.id,
                    "lexicon_id": lemma.lexicon_id,
                    "external_key": lemma.external_key,
                    "lemma": lemma.lemma,
                    "normalized_lemma": lemma.normalized_lemma,
                    "part_of_speech": lemma.part_of_speech,
                    "key_tags": lemma.key_tags,
                    "is_standard": lemma.is_standard,
                    "is_active": True,
                }
            elif lemma.is_standard:
                row["is_standard"] = True

            word_form = record.word_form
            form_rows[word_form.id] = {
                "id": word_form.id,
                "lemma_id": word_form.lemma_id,
                "form": word_form.form,
                "normalized_form": word_form.normalized_form,
                "morphology": word_form.morphology,
                "morphology_tags": word_form.morphology_tags,
                "morphology_features": word_form.morphology_features,
                "is_standard": word_form.is_standard,
                "is_active": True,
            }

        lemma_insert = insert(reference_lemmas).values(list(lemma_rows.values()))
        self._session.execute(
            lemma_insert.on_conflict_do_update(
                index_elements=[reference_lemmas.c.id],
                set_={
                    "lemma": lemma_insert.excluded.lemma,
                    "normalized_lemma": lemma_insert.excluded.normalized_lemma,
                    "part_of_speech": lemma_insert.excluded.part_of_speech,
                    "key_tags": lemma_insert.excluded.key_tags,
                    "is_standard": (
                        reference_lemmas.c.is_standard
                        | lemma_insert.excluded.is_standard
                    ),
                    "is_active": True,
                },
            )
        )

        form_insert = insert(reference_word_forms).values(list(form_rows.values()))
        self._session.execute(
            form_insert.on_conflict_do_update(
                index_elements=[reference_word_forms.c.id],
                set_={
                    "form": form_insert.excluded.form,
                    "normalized_form": form_insert.excluded.normalized_form,
                    "morphology": form_insert.excluded.morphology,
                    "morphology_tags": form_insert.excluded.morphology_tags,
                    "morphology_features": form_insert.excluded.morphology_features,
                    "is_standard": form_insert.excluded.is_standard,
                    "is_active": True,
                },
            )
        )


class SqlAlchemyReferenceLexiconUnitOfWork:
    """Session-backed transaction for reference lexical data."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.reference_lexicon: SqlAlchemyReferenceLexiconRepository

    def __enter__(self) -> "SqlAlchemyReferenceLexiconUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.reference_lexicon = SqlAlchemyReferenceLexiconRepository(self._session)
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
            raise RuntimeError("reference-lexicon unit of work has not been entered")
        self._session.commit()


def create_reference_lexicon_unit_of_work_factory(
    engine: Engine,
) -> ReferenceLexiconUnitOfWorkFactory:
    """Build one fresh reference-data transaction per use case."""

    return lambda: SqlAlchemyReferenceLexiconUnitOfWork(engine)
