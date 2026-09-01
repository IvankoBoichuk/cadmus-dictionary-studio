"""SQLAlchemy persistence for the async processing-task registry."""

from collections.abc import Sequence
from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry

from cadmus.infrastructure.database import metadata
from cadmus.processing.domain import (
    ProcessingTask,
    ProcessingTaskKind,
    ProcessingTaskStatus,
)
from cadmus.processing.ports import ProcessingTaskUnitOfWorkFactory

processing_registry = registry(metadata=metadata)

processing_tasks = Table(
    "processing_tasks",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("kind", String(32), nullable=False),
    Column("celery_task_id", String(128), nullable=False),
    Column("status", String(16), nullable=False),
    Column("target_id", Uuid(as_uuid=True), nullable=True),
    Column("target_label", String(255), nullable=True),
    Column("rerun_params", JSONB, nullable=False, default=dict),
    Column("error", Text, nullable=True),
    Column("result", JSONB, nullable=True),
    Column(
        "enqueued_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "retry_of_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.processing_tasks.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("celery_task_id", name="uq_processing_tasks_celery_task_id"),
)

processing_registry.map_imperatively(ProcessingTask, processing_tasks)


class SqlAlchemyProcessingTaskRepository:
    """Processing-task registry backed by a caller-owned session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: ProcessingTask) -> None:
        self._session.add(task)

    def get(self, task_id: UUID) -> ProcessingTask | None:
        return self._session.get(ProcessingTask, task_id)

    def get_by_celery_id(self, celery_task_id: str) -> ProcessingTask | None:
        return self._session.scalar(
            select(ProcessingTask).where(
                processing_tasks.c.celery_task_id == celery_task_id
            )
        )

    def list_for_dictionary(
        self,
        dictionary_id: UUID,
        *,
        kinds: Sequence[ProcessingTaskKind] | None = None,
        statuses: Sequence[ProcessingTaskStatus] | None = None,
        limit: int = 100,
    ) -> list[ProcessingTask]:
        statement = select(ProcessingTask).where(
            processing_tasks.c.dictionary_id == dictionary_id
        )
        if kinds:
            statement = statement.where(
                processing_tasks.c.kind.in_([str(kind) for kind in kinds])
            )
        if statuses:
            statement = statement.where(
                processing_tasks.c.status.in_([str(status) for status in statuses])
            )
        statement = statement.order_by(processing_tasks.c.created_at.desc()).limit(
            limit
        )
        return list(self._session.scalars(statement))

    def update(self, task: ProcessingTask) -> None:
        self._session.add(task)

    def prune_dictionary(self, dictionary_id: UUID, *, keep: int) -> None:
        keep_ids = (
            select(processing_tasks.c.id)
            .where(processing_tasks.c.dictionary_id == dictionary_id)
            .order_by(processing_tasks.c.created_at.desc())
            .limit(keep)
            .scalar_subquery()
        )
        self._session.execute(
            delete(processing_tasks).where(
                processing_tasks.c.dictionary_id == dictionary_id,
                processing_tasks.c.id.not_in(keep_ids),
            )
        )


class SqlAlchemyProcessingTaskUnitOfWork:
    """Session-backed transaction for the processing-task registry."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.processing_tasks: SqlAlchemyProcessingTaskRepository

    def __enter__(self) -> "SqlAlchemyProcessingTaskUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.processing_tasks = SqlAlchemyProcessingTaskRepository(self._session)
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
            raise RuntimeError("processing-task unit of work has not been entered")
        self._session.commit()


def create_processing_unit_of_work_factory(
    engine: Engine,
) -> ProcessingTaskUnitOfWorkFactory:
    """Build one fresh processing-task transaction per use case."""

    return lambda: SqlAlchemyProcessingTaskUnitOfWork(engine)
