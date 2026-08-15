"""SQLAlchemy persistence adapters for the identity module."""

from types import TracebackType
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Table,
    Uuid,
    delete,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, registry

from cadmus.identity import (
    AccountStatus,
    AuthenticatedSession,
    DuplicateEmailError,
    IdentityUnitOfWorkFactory,
    PasswordResetToken,
    User,
    VerificationToken,
)
from cadmus.infrastructure.database import metadata

identity_registry = registry(metadata=metadata)

users = Table(
    "users",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column(
        "status",
        Enum(
            AccountStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
            native_enum=False,
            length=32,
        ),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("activated_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "status IN ('pending_verification', 'active')",
        name="account_status",
    ),
)

verification_tokens = Table(
    "email_verification_tokens",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("token_digest", String(64), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True), nullable=True),
)

password_reset_tokens = Table(
    "password_reset_tokens",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("token_digest", String(64), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True), nullable=True),
)

authenticated_sessions = Table(
    "authenticated_sessions",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("cadmus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("token_digest", String(64), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

identity_registry.map_imperatively(User, users)
identity_registry.map_imperatively(VerificationToken, verification_tokens)
identity_registry.map_imperatively(PasswordResetToken, password_reset_tokens)
identity_registry.map_imperatively(AuthenticatedSession, authenticated_sessions)


class SqlAlchemyIdentityRepository:
    """Identity repository backed by one caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(users.c.email == email))

    def get_user(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_verification_token(self, token_digest: str) -> VerificationToken | None:
        statement = (
            select(VerificationToken)
            .where(verification_tokens.c.token_digest == token_digest)
            .with_for_update()
        )
        return self._session.scalar(statement)

    def get_password_reset_token(self, token_digest: str) -> PasswordResetToken | None:
        statement = (
            select(PasswordResetToken)
            .where(password_reset_tokens.c.token_digest == token_digest)
            .with_for_update()
        )
        return self._session.scalar(statement)

    def get_session(self, token_digest: str) -> AuthenticatedSession | None:
        return self._session.scalar(
            select(AuthenticatedSession).where(
                authenticated_sessions.c.token_digest == token_digest
            )
        )

    def add_user(self, user: User) -> None:
        self._session.add(user)
        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()
            raise DuplicateEmailError from error

    def add_verification_token(self, token: VerificationToken) -> None:
        self._session.add(token)

    def add_password_reset_token(self, token: PasswordResetToken) -> None:
        self._session.add(token)

    def add_session(self, session: AuthenticatedSession) -> None:
        self._session.add(session)

    def delete_session(self, token_digest: str) -> None:
        self._session.execute(
            delete(authenticated_sessions).where(
                authenticated_sessions.c.token_digest == token_digest
            )
        )

    def delete_sessions_for_user(self, user_id: UUID) -> None:
        self._session.execute(
            delete(authenticated_sessions).where(
                authenticated_sessions.c.user_id == user_id
            )
        )


class SqlAlchemyIdentityUnitOfWork:
    """Session-backed identity transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self.users: SqlAlchemyIdentityRepository

    def __enter__(self) -> "SqlAlchemyIdentityUnitOfWork":
        self._session = Session(self._engine, expire_on_commit=False)
        self.users = SqlAlchemyIdentityRepository(self._session)
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
            raise RuntimeError("identity unit of work has not been entered")
        self._session.commit()


def create_identity_unit_of_work_factory(
    engine: Engine,
) -> IdentityUnitOfWorkFactory:
    """Return a zero-argument transaction factory bound to an engine."""
    return lambda: SqlAlchemyIdentityUnitOfWork(engine)
