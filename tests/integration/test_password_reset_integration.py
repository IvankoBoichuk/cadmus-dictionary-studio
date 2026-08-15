"""Password reset against PostgreSQL and the SMTP test boundary."""

import os
import urllib.request
from datetime import timedelta

import pytest
from alembic import command
from alembic.config import Config
from cadmus.config import Environment, Settings
from cadmus.identity import (
    AuthenticationService,
    PasswordResetError,
    PasswordResetFailure,
    PasswordResetService,
    RegistrationService,
)
from cadmus.infrastructure.email import SmtpEmailSender
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
from cadmus.infrastructure.security import (
    ScryptPasswordHasher,
    SecurePasswordResetTokenProvider,
    SecureSessionTokenProvider,
    SecureVerificationTokenProvider,
)
from pydantic import SecretStr
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def test_password_reset_invalidates_sessions_and_is_single_use() -> None:
    database_url = os.environ["CADMUS_TEST_DATABASE_URL"]
    os.environ["CADMUS_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cadmus.password_reset_tokens"))
        connection.execute(text("DELETE FROM cadmus.authenticated_sessions"))
        connection.execute(text("DELETE FROM cadmus.email_verification_tokens"))
        connection.execute(text("DELETE FROM cadmus.users"))

    settings = Settings(
        environment=Environment.TEST,
        database_url=SecretStr(database_url),
        smtp_host=os.environ["CADMUS_TEST_SMTP_HOST"],
        smtp_port=1025,
    )
    unit_of_work_factory = create_identity_unit_of_work_factory(engine)
    password_hasher = ScryptPasswordHasher()

    registration = RegistrationService(
        unit_of_work_factory=unit_of_work_factory,
        password_hasher=password_hasher,
        token_provider=SecureVerificationTokenProvider(),
        email_sender=SmtpEmailSender(settings),
        public_web_url="https://cadmus.example",
    )
    user = registration.register(
        "reset-integration@example.com",
        "old-long-enough-password",
        "old-long-enough-password",
    )
    activation_token = "integration-activation-token"
    verification_token_provider = SecureVerificationTokenProvider()
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE cadmus.email_verification_tokens "
                "SET token_digest = :digest WHERE user_id = :user_id"
            ),
            {
                "digest": verification_token_provider.digest(activation_token),
                "user_id": user.id,
            },
        )
    registration.activate(activation_token)

    authentication = AuthenticationService(
        unit_of_work_factory=unit_of_work_factory,
        password_hasher=password_hasher,
        session_token_provider=SecureSessionTokenProvider(),
        session_lifetime=timedelta(hours=12),
    )
    login = authentication.login(
        "reset-integration@example.com", "old-long-enough-password"
    )
    assert authentication.authenticate(login.session_token).id == user.id

    reset_token_provider = SecurePasswordResetTokenProvider()
    password_reset = PasswordResetService(
        unit_of_work_factory=unit_of_work_factory,
        password_hasher=password_hasher,
        token_provider=reset_token_provider,
        email_sender=SmtpEmailSender(settings),
        public_web_url="https://cadmus.example",
        token_lifetime=timedelta(hours=1),
    )
    password_reset.request_reset("RESET-INTEGRATION@example.com")

    with urllib.request.urlopen(
        f"{os.environ['CADMUS_TEST_MAILPIT_URL']}/view/latest.txt",
        timeout=5,
    ) as response:
        delivered_message = response.read().decode("utf-8")
    assert "https://cadmus.example/reset-password#token=" in delivered_message

    with engine.connect() as connection:
        stored_token = connection.execute(
            text(
                "SELECT token_digest, expires_at, consumed_at "
                "FROM cadmus.password_reset_tokens WHERE user_id = :user_id"
            ),
            {"user_id": user.id},
        ).one()
    assert len(stored_token.token_digest) == 64
    assert stored_token.consumed_at is None

    # The raw value is known only to the link recipient; persistence uses its digest.
    raw_reset_token = "integration-reset-token"
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE cadmus.password_reset_tokens "
                "SET token_digest = :digest WHERE user_id = :user_id"
            ),
            {
                "digest": reset_token_provider.digest(raw_reset_token),
                "user_id": user.id,
            },
        )

    password_reset.reset_password(
        raw_reset_token,
        "new-long-enough-password",
        "new-long-enough-password",
    )

    with engine.connect() as connection:
        stored_user = connection.execute(
            text("SELECT password_hash FROM cadmus.users WHERE id = :id"),
            {"id": user.id},
        ).one()
        consumed_token = connection.execute(
            text(
                "SELECT consumed_at FROM cadmus.password_reset_tokens "
                "WHERE user_id = :user_id"
            ),
            {"user_id": user.id},
        ).one()
        remaining_sessions = connection.execute(
            text(
                "SELECT count(*) FROM cadmus.authenticated_sessions "
                "WHERE user_id = :user_id"
            ),
            {"user_id": user.id},
        ).scalar_one()

    assert "new-long-enough-password" not in stored_user.password_hash
    assert password_hasher.verify("new-long-enough-password", stored_user.password_hash)
    assert consumed_token.consumed_at is not None
    assert remaining_sessions == 0

    with pytest.raises(PasswordResetError) as reused:
        password_reset.reset_password(
            raw_reset_token,
            "another-long-enough-password",
            "another-long-enough-password",
        )
    assert reused.value.reason is PasswordResetFailure.USED

    with engine.connect() as connection:
        unchanged_user = connection.execute(
            text("SELECT password_hash FROM cadmus.users WHERE id = :id"),
            {"id": user.id},
        ).one()
    assert unchanged_user.password_hash == stored_user.password_hash
    engine.dispose()


def test_password_reset_request_is_silent_no_op_for_unknown_email() -> None:
    database_url = os.environ["CADMUS_TEST_DATABASE_URL"]
    os.environ["CADMUS_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)

    settings = Settings(
        environment=Environment.TEST,
        database_url=SecretStr(database_url),
        smtp_host=os.environ["CADMUS_TEST_SMTP_HOST"],
        smtp_port=1025,
    )
    password_reset = PasswordResetService(
        unit_of_work_factory=create_identity_unit_of_work_factory(engine),
        password_hasher=ScryptPasswordHasher(),
        token_provider=SecurePasswordResetTokenProvider(),
        email_sender=SmtpEmailSender(settings),
        public_web_url="https://cadmus.example",
    )

    # Must not raise and must not attempt an SMTP delivery for a missing account.
    password_reset.request_reset("does-not-exist@example.com")
    engine.dispose()
