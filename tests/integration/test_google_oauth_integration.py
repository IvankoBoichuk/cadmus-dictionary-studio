"""Google OAuth login against a real PostgreSQL identity schema.

Google's live OAuth/OIDC endpoints are never called here: a fake
``GoogleOAuthClient`` stands in for the network boundary so this test only
exercises the database round-trip (BH-188 identity linking and constraints).
"""

import os
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cadmus.identity import (
    AuthenticationService,
    GoogleAuthenticationService,
    GoogleIdentityClaims,
)
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
from cadmus.infrastructure.security import (
    ScryptPasswordHasher,
    SecureSessionTokenProvider,
)
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


class FakeGoogleOAuthClient:
    def __init__(self, claims: GoogleIdentityClaims) -> None:
        self._claims = claims

    def build_authorization_url(
        self, state: str, nonce: str, code_challenge: str
    ) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth?mock=1"

    def exchange_code(
        self, code: str, code_verifier: str, expected_nonce: str
    ) -> GoogleIdentityClaims:
        return self._claims


def _google_service(
    engine: Engine, claims: GoogleIdentityClaims
) -> GoogleAuthenticationService:
    unit_of_work_factory = create_identity_unit_of_work_factory(engine)
    authentication_service = AuthenticationService(
        unit_of_work_factory=unit_of_work_factory,
        password_hasher=ScryptPasswordHasher(),
        session_token_provider=SecureSessionTokenProvider(),
        session_lifetime=timedelta(hours=12),
    )
    return GoogleAuthenticationService(
        unit_of_work_factory=unit_of_work_factory,
        google_oauth_client=FakeGoogleOAuthClient(claims),
        authentication_service=authentication_service,
    )


def test_google_login_creates_links_and_reuses_identities_in_postgres() -> None:
    database_url = os.environ["CADMUS_TEST_DATABASE_URL"]
    os.environ["CADMUS_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cadmus.google_identities"))
        connection.execute(text("DELETE FROM cadmus.authenticated_sessions"))
        connection.execute(text("DELETE FROM cadmus.users"))

    # 1. A brand-new Google identity creates a password-less active user.
    new_user_claims = GoogleIdentityClaims(
        subject="integration-subject-new",
        email="new.google.user@example.com",
        email_verified=True,
    )
    result = _google_service(engine, new_user_claims).complete_login(
        code="code",
        state="state",
        expected_state="state",
        expected_nonce="nonce",
        code_verifier="verifier",
    )
    with engine.connect() as connection:
        stored_user = connection.execute(
            text(
                "SELECT email, password_hash, status FROM cadmus.users WHERE id = :id"
            ),
            {"id": result.user.id},
        ).one()
        stored_identity = connection.execute(
            text(
                "SELECT user_id, subject, email FROM cadmus.google_identities "
                "WHERE subject = :subject"
            ),
            {"subject": "integration-subject-new"},
        ).one()
        user_count = connection.execute(
            text("SELECT count(*) FROM cadmus.users")
        ).scalar_one()

    assert stored_user.email == "new.google.user@example.com"
    assert stored_user.password_hash is None
    assert stored_user.status == "active"
    assert stored_identity.user_id == result.user.id
    assert user_count == 1

    # 2. Signing in again with the same Google subject reuses the same user.
    repeat_result = _google_service(engine, new_user_claims).complete_login(
        code="code",
        state="state",
        expected_state="state",
        expected_nonce="nonce",
        code_verifier="verifier",
    )
    with engine.connect() as connection:
        user_count_after_repeat = connection.execute(
            text("SELECT count(*) FROM cadmus.users")
        ).scalar_one()
        identity_count = connection.execute(
            text(
                "SELECT count(*) FROM cadmus.google_identities WHERE subject = :subject"
            ),
            {"subject": "integration-subject-new"},
        ).scalar_one()

    assert repeat_result.user.id == result.user.id
    assert user_count_after_repeat == 1
    assert identity_count == 1

    # 3. A verified Google email matching an existing password account links
    #    to it instead of creating a duplicate.
    password_user_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cadmus.users "
                "(id, email, password_hash, status, created_at) "
                "VALUES (:id, :email, :password_hash, 'active', now())"
            ),
            {
                "id": password_user_id,
                "email": "already.registered@example.com",
                "password_hash": ScryptPasswordHasher().hash("correct-password"),
            },
        )

    link_claims = GoogleIdentityClaims(
        subject="integration-subject-link",
        email="already.registered@example.com",
        email_verified=True,
    )
    link_result = _google_service(engine, link_claims).complete_login(
        code="code",
        state="state",
        expected_state="state",
        expected_nonce="nonce",
        code_verifier="verifier",
    )
    with engine.connect() as connection:
        user_count_after_link = connection.execute(
            text("SELECT count(*) FROM cadmus.users")
        ).scalar_one()

    assert link_result.user.id == password_user_id
    assert user_count_after_link == 2

    # 4. The subject column is unique: a second user cannot claim it.
    with (
        pytest.raises(IntegrityError),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO cadmus.google_identities "
                "(id, user_id, subject, email, created_at) "
                "VALUES (:id, :user_id, :subject, :email, now())"
            ),
            {
                "id": uuid4(),
                "user_id": password_user_id,
                "subject": "integration-subject-new",
                "email": "collides@example.com",
            },
        )

    engine.dispose()
