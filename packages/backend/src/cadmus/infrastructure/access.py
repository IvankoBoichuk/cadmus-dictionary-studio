"""SQLAlchemy persistence adapters for the access-control module."""

from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
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

from cadmus.access.domain import ProjectMembership
from cadmus.access.ports import MembershipsUnitOfWorkFactory
from cadmus.infrastructure.database import metadata

access_registry = registry(metadata=metadata)

project_memberships = Table(
    "project_memberships",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "dictionary_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("role", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column(
        "updated_by",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    CheckConstraint(
        "role IN ('editor', 'reviewer', 'viewer')", name="project_membership_role"
    ),
    UniqueConstraint(
        "dictionary_id", "user_id", name="uq_project_memberships_dictionary_id_user_id"
    ),
)

access_registry.map_imperatively(ProjectMembership, project_memberships)


class SqlAlchemyMembershipsRepository:
    """Memberships repository backed by one caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_membership(
        self, dictionary_id: UUID, user_id: UUID
    ) -> ProjectMembership | None:
        return self._session.scalar(
            select(ProjectMembership).where(
                project_memberships.c.dictionary_id == dictionary_id,
                project_memberships.c.user_id == user_id,
            )
        )

    def list_members(self, dictionary_id: UUID) -> list[ProjectMembership]:
        return list(
            self._session.scalars(
                select(ProjectMembership)
                .where(project_memberships.c.dictionary_id == dictionary_id)
                .order_by(project_memberships.c.created_at)
            )
        )

    def list_memberships_for_user(self, user_id: UUID) -> list[ProjectMembership]:
        return list(
            self._session.scalars(
                select(ProjectMembership).where(
                    project_memberships.c.user_id == user_id
                )
            )
        )

    def add_member(self, membership: ProjectMembership) -> None:
        self._session.add(membership)

    def update_member(self, membership: ProjectMembership) -> None:
        self._session.add(membership)

    def remove_member(self, dictionary_id: UUID, user_id: UUID) -> None:
        self._session.execute(
            delete(project_memberships).where(
                project_memberships.c.dictionary_id == dictionary_id,
                project_memberships.c.user_id == user_id,
            )
        )


class SqlAlchemyMembershipsUnitOfWork:
    """Session-backed access-control transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.memberships: SqlAlchemyMembershipsRepository

    def __enter__(self) -> "SqlAlchemyMembershipsUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.memberships = SqlAlchemyMembershipsRepository(self._session)
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
            raise RuntimeError("access unit of work has not been entered")
        self._session.commit()


def create_access_unit_of_work_factory(
    engine: Engine,
) -> MembershipsUnitOfWorkFactory:
    """Return a zero-argument transaction factory bound to an engine."""
    return lambda: SqlAlchemyMembershipsUnitOfWork(engine)
