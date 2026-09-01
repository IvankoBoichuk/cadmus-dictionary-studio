"""Registration and activation against PostgreSQL and the SMTP test boundary."""

import os
from datetime import timedelta

import pytest
from alembic import command
from alembic.config import Config
from cadmus.config import Environment, Settings
from cadmus.identity import (
    ActivationError,
    ActivationFailure,
    AuthenticationError,
    AuthenticationService,
    RegistrationService,
)
from cadmus.infrastructure.email import SmtpEmailSender
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
from cadmus.infrastructure.security import (
    ScryptPasswordHasher,
    SecureSessionTokenProvider,
    SecureVerificationTokenProvider,
)
from pydantic import SecretStr
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


class FailingEmailSender:
    def send_verification(self, recipient: str, verification_url: str) -> None:
        raise ConnectionError("SMTP is unavailable")

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        raise ConnectionError("SMTP is unavailable")

    def send_email_change(self, recipient: str, confirm_url: str) -> None:
        raise ConnectionError("SMTP is unavailable")


def test_registration_persists_only_protected_credentials_and_activates_once() -> None:
    database_url = os.environ["CADMUS_TEST_DATABASE_URL"]
    os.environ["CADMUS_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cadmus.email_verification_tokens"))
        connection.execute(text("DELETE FROM cadmus.users"))

    settings = Settings(
        environment=Environment.TEST,
        database_url=SecretStr(database_url),
        smtp_host=os.environ["CADMUS_TEST_SMTP_HOST"],
        smtp_port=1025,
    )
    token_provider = SecureVerificationTokenProvider()
    failed_service = RegistrationService(
        unit_of_work_factory=create_identity_unit_of_work_factory(engine),
        password_hasher=ScryptPasswordHasher(),
        token_provider=token_provider,
        email_sender=FailingEmailSender(),
        public_web_url="https://cadmus.example",
    )
    with pytest.raises(ConnectionError, match="SMTP is unavailable"):
        failed_service.register(
            "failed-delivery@example.com",
            "long-enough-password",
            "long-enough-password",
        )
    with engine.connect() as connection:
        failed_user_count = connection.execute(
            text("SELECT count(*) FROM cadmus.users")
        ).scalar_one()
    assert failed_user_count == 0

    service = RegistrationService(
        unit_of_work_factory=create_identity_unit_of_work_factory(engine),
        password_hasher=ScryptPasswordHasher(),
        token_provider=token_provider,
        email_sender=SmtpEmailSender(settings),
        public_web_url="https://cadmus.example",
        token_lifetime=timedelta(hours=24),
    )

    user = service.register(
        "integration@example.com",
        "long-enough-password",
        "long-enough-password",
    )

    with engine.connect() as connection:
        stored_user = connection.execute(
            text(
                "SELECT email, password_hash, status FROM cadmus.users WHERE id = :id"
            ),
            {"id": user.id},
        ).one()
        stored_token = connection.execute(
            text(
                "SELECT token_digest, expires_at, consumed_at "
                "FROM cadmus.email_verification_tokens WHERE user_id = :user_id"
            ),
            {"user_id": user.id},
        ).one()

    assert stored_user.email == "integration@example.com"
    assert stored_user.status == "pending_verification"
    assert "long-enough-password" not in stored_user.password_hash
    assert len(stored_token.token_digest) == 64
    assert stored_token.consumed_at is None

    # The raw value is known only to the link recipient; persistence uses its digest.
    raw_token = "integration-activation-token"
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE cadmus.email_verification_tokens "
                "SET token_digest = :digest WHERE user_id = :user_id"
            ),
            {"digest": token_provider.digest(raw_token), "user_id": user.id},
        )

    activated = service.activate(raw_token)
    assert activated.status.value == "active"

    authentication = AuthenticationService(
        unit_of_work_factory=create_identity_unit_of_work_factory(engine),
        password_hasher=ScryptPasswordHasher(),
        session_token_provider=SecureSessionTokenProvider(),
        session_lifetime=timedelta(hours=12),
    )
    login = authentication.login("INTEGRATION@example.com", "long-enough-password")
    assert authentication.authenticate(login.session_token).id == user.id
    with engine.connect() as connection:
        stored_session = connection.execute(
            text(
                "SELECT token_digest, expires_at FROM cadmus.authenticated_sessions "
                "WHERE user_id = :user_id"
            ),
            {"user_id": user.id},
        ).one()
    assert login.session_token not in stored_session.token_digest
    assert len(stored_session.token_digest) == 64

    authentication.logout(login.session_token)
    with pytest.raises(AuthenticationError):
        authentication.authenticate(login.session_token)
    with engine.connect() as connection:
        remaining_sessions = connection.execute(
            text(
                "SELECT count(*) FROM cadmus.authenticated_sessions "
                "WHERE user_id = :user_id"
            ),
            {"user_id": user.id},
        ).scalar_one()
    assert remaining_sessions == 0

    with pytest.raises(ActivationError) as reused:
        service.activate(raw_token)
    assert reused.value.reason is ActivationFailure.USED
    engine.dispose()
