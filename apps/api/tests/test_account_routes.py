from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.identity import (
    AccountService,
    AccountStatus,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    EmailChangeError,
    EmailChangeFailure,
    EmailChangeValidationError,
    PasswordResetValidationError,
    ProfileValidationError,
    RegistrationService,
    SessionNotFoundError,
    SessionView,
    User,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

USER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")


def _user(name: str | None = None) -> User:
    return User(
        id=USER_ID,
        email="user@example.com",
        password_hash="unused",
        status=AccountStatus.ACTIVE,
        created_at=datetime.now(UTC),
        activated_at=datetime.now(UTC),
        name=name,
    )


@dataclass
class StubRegistrationService:
    def register(self, email: str, password: str, confirmation: str) -> User:
        raise AssertionError("not used by account tests")

    def activate(self, token: str) -> User:
        raise AssertionError("not used by account tests")


@dataclass
class StubAuthenticationService:
    session_error: AuthenticationError | None = None
    seen_tokens: list[str] = field(default_factory=list)

    def login(self, email: str, password: str, user_agent: str | None = None) -> object:
        raise AssertionError("not used by account tests")

    def authenticate(self, token: str) -> User:
        self.seen_tokens.append(token)
        if self.session_error is not None:
            raise self.session_error
        return _user()

    def logout(self, token: str) -> None:
        raise AssertionError("not used by account tests")


@dataclass
class StubAccountService:
    profile_error: ProfileValidationError | None = None
    password_error: AuthenticationError | PasswordResetValidationError | None = None
    email_error: AuthenticationError | EmailChangeValidationError | None = None
    confirm_error: EmailChangeError | None = None
    revoke_error: SessionNotFoundError | None = None
    sessions: list[SessionView] = field(default_factory=list)
    revoked_others: int = 0
    calls: dict[str, object] = field(default_factory=dict)

    def update_profile(self, user_id: UUID, name: str | None) -> User:
        self.calls["update_profile"] = (user_id, name)
        if self.profile_error is not None:
            raise self.profile_error
        return _user(name=name)

    def change_password(
        self,
        *,
        user_id: UUID,
        current_raw_token: str,
        current_password: str,
        new_password: str,
        new_password_confirmation: str,
    ) -> None:
        self.calls["change_password"] = (
            user_id,
            current_raw_token,
            current_password,
            new_password,
            new_password_confirmation,
        )
        if self.password_error is not None:
            raise self.password_error

    def request_email_change(
        self, user_id: UUID, new_email: str, current_password: str
    ) -> None:
        self.calls["request_email_change"] = (user_id, new_email, current_password)
        if self.email_error is not None:
            raise self.email_error

    def confirm_email_change(self, raw_token: str) -> None:
        self.calls["confirm_email_change"] = raw_token
        if self.confirm_error is not None:
            raise self.confirm_error

    def list_sessions(self, user_id: UUID, current_raw_token: str) -> list[SessionView]:
        self.calls["list_sessions"] = (user_id, current_raw_token)
        return self.sessions

    def revoke_session(self, user_id: UUID, session_id: UUID) -> None:
        self.calls["revoke_session"] = (user_id, session_id)
        if self.revoke_error is not None:
            raise self.revoke_error

    def revoke_other_sessions(self, user_id: UUID, current_raw_token: str) -> int:
        self.calls["revoke_other_sessions"] = (user_id, current_raw_token)
        return self.revoked_others


def client_for(
    account: StubAccountService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            registration_service=cast(RegistrationService, StubRegistrationService()),
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            account_service=cast(AccountService, account or StubAccountService()),
        )
    )


def _authed(client: TestClient) -> None:
    client.cookies.set("cadmus_session", "browser-token")


# --- auth guard ---------------------------------------------------------


def test_account_endpoints_require_a_session_cookie() -> None:
    with client_for() as client:
        assert client.get("/auth/account").status_code == 401
        assert client.get("/auth/sessions").status_code == 401
        assert client.post("/auth/sessions/revoke-others").status_code == 401


def test_account_endpoint_rejects_an_invalid_session() -> None:
    authentication = StubAuthenticationService(
        session_error=AuthenticationError(AuthenticationFailure.INVALID_SESSION)
    )
    with client_for(authentication=authentication) as client:
        _authed(client)
        assert client.get("/auth/account").status_code == 401


# --- profile ----------------------------------------------------------


def test_get_account_returns_editable_fields() -> None:
    with client_for() as client:
        _authed(client)
        response = client.get("/auth/account")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(USER_ID),
        "email": "user@example.com",
        "name": None,
    }


def test_patch_account_updates_name() -> None:
    account = StubAccountService()
    with client_for(account) as client:
        _authed(client)
        response = client.patch("/auth/account", json={"name": "Ada Lovelace"})

    assert response.status_code == 200
    assert response.json()["name"] == "Ada Lovelace"
    assert account.calls["update_profile"] == (USER_ID, "Ada Lovelace")


def test_patch_account_reports_field_errors() -> None:
    account = StubAccountService(
        profile_error=ProfileValidationError({"name": "Задовге ім'я."})
    )
    with client_for(account) as client:
        _authed(client)
        response = client.patch("/auth/account", json={"name": "x"})

    assert response.status_code == 422
    assert response.json() == {"errors": {"name": "Задовге ім'я."}}


# --- change password ------------------------------------------------


def test_change_password_forwards_current_session_token() -> None:
    account = StubAccountService()
    with client_for(account) as client:
        _authed(client)
        response = client.post(
            "/auth/account/change-password",
            json={
                "current_password": "old-password",
                "new_password": "a-brand-new-password",
                "new_password_confirmation": "a-brand-new-password",
            },
        )

    assert response.status_code == 200
    assert account.calls["change_password"] == (
        USER_ID,
        "browser-token",
        "old-password",
        "a-brand-new-password",
        "a-brand-new-password",
    )
    assert "a-brand-new-password" not in str(response.request.url)


def test_change_password_rejects_wrong_current_password_with_403() -> None:
    account = StubAccountService(
        password_error=AuthenticationError(AuthenticationFailure.INVALID_CREDENTIALS)
    )
    with client_for(account) as client:
        _authed(client)
        response = client.post(
            "/auth/account/change-password",
            json={
                "current_password": "wrong",
                "new_password": "a-brand-new-password",
                "new_password_confirmation": "a-brand-new-password",
            },
        )

    assert response.status_code == 403
    assert response.json()["code"] == "invalid_credentials"


def test_change_password_rejects_weak_new_password_with_field_errors() -> None:
    account = StubAccountService(
        password_error=PasswordResetValidationError({"password": "Закоротко."})
    )
    with client_for(account) as client:
        _authed(client)
        response = client.post(
            "/auth/account/change-password",
            json={
                "current_password": "old-password",
                "new_password": "short",
                "new_password_confirmation": "short",
            },
        )

    assert response.status_code == 422
    assert response.json() == {"errors": {"password": "Закоротко."}}


# --- change email --------------------------------------------------


def test_change_email_accepts_request_and_returns_notice() -> None:
    account = StubAccountService()
    with client_for(account) as client:
        _authed(client)
        response = client.post(
            "/auth/account/change-email",
            json={"new_email": "new@example.com", "current_password": "old-password"},
        )

    assert response.status_code == 200
    assert "message" in response.json()
    assert account.calls["request_email_change"] == (
        USER_ID,
        "new@example.com",
        "old-password",
    )


def test_change_email_reports_taken_address_as_field_error() -> None:
    account = StubAccountService(
        email_error=EmailChangeValidationError(
            {"new_email": "Ця email-адреса вже зареєстрована."}
        )
    )
    with client_for(account) as client:
        _authed(client)
        response = client.post(
            "/auth/account/change-email",
            json={"new_email": "taken@example.com", "current_password": "old-password"},
        )

    assert response.status_code == 422
    assert "new_email" in response.json()["errors"]


def test_change_email_rejects_wrong_password_with_403() -> None:
    account = StubAccountService(
        email_error=AuthenticationError(AuthenticationFailure.INVALID_CREDENTIALS)
    )
    with client_for(account) as client:
        _authed(client)
        response = client.post(
            "/auth/account/change-email",
            json={"new_email": "new@example.com", "current_password": "wrong"},
        )

    assert response.status_code == 403


# --- confirm email change (public) -------------------------------


def test_confirm_email_change_succeeds() -> None:
    account = StubAccountService()
    with client_for(account) as client:
        response = client.post(
            "/auth/confirm-email-change", json={"token": "one-time-token"}
        )

    assert response.status_code == 200
    assert account.calls["confirm_email_change"] == "one-time-token"
    assert "one-time-token" not in str(response.request.url)


@pytest.mark.parametrize(
    ("reason", "expected_message"),
    [
        (EmailChangeFailure.INVALID, "Посилання для зміни email недійсне."),
        (EmailChangeFailure.EXPIRED, "Термін дії посилання минув."),
        (EmailChangeFailure.USED, "Це посилання вже було використано."),
    ],
)
def test_confirm_email_change_returns_controlled_token_failures(
    reason: EmailChangeFailure, expected_message: str
) -> None:
    account = StubAccountService(confirm_error=EmailChangeError(reason))
    with client_for(account) as client:
        response = client.post(
            "/auth/confirm-email-change", json={"token": "one-time-token"}
        )

    assert response.status_code == 400
    assert response.json() == {"code": reason, "message": expected_message}


# --- sessions ----------------------------------------------------


def test_list_sessions_serialises_current_flag() -> None:
    now = datetime.now(UTC)
    account = StubAccountService(
        sessions=[
            SessionView(
                id=uuid4(),
                created_at=now,
                expires_at=now + timedelta(hours=6),
                user_agent="Firefox",
                is_current=True,
            ),
            SessionView(
                id=uuid4(),
                created_at=now - timedelta(days=1),
                expires_at=now + timedelta(hours=1),
                user_agent=None,
                is_current=False,
            ),
        ]
    )
    with client_for(account) as client:
        _authed(client)
        response = client.get("/auth/sessions")

    assert response.status_code == 200
    body = response.json()["sessions"]
    assert [s["current"] for s in body] == [True, False]
    assert body[0]["user_agent"] == "Firefox"
    assert body[1]["user_agent"] is None
    assert account.calls["list_sessions"] == (USER_ID, "browser-token")


def test_revoke_session_returns_204() -> None:
    account = StubAccountService()
    session_id = uuid4()
    with client_for(account) as client:
        _authed(client)
        response = client.delete(f"/auth/sessions/{session_id}")

    assert response.status_code == 204
    assert account.calls["revoke_session"] == (USER_ID, session_id)


def test_revoke_unknown_session_returns_404() -> None:
    account = StubAccountService(revoke_error=SessionNotFoundError())
    with client_for(account) as client:
        _authed(client)
        response = client.delete(f"/auth/sessions/{uuid4()}")

    assert response.status_code == 404


def test_revoke_other_sessions_reports_count() -> None:
    account = StubAccountService(revoked_others=3)
    with client_for(account) as client:
        _authed(client)
        response = client.post("/auth/sessions/revoke-others")

    assert response.status_code == 200
    assert response.json() == {"revoked": 3}
    assert account.calls["revoke_other_sessions"] == (USER_ID, "browser-token")


def test_openapi_documents_account_contracts() -> None:
    with client_for() as client:
        schema = client.get("/openapi.json").json()

    paths = schema["paths"]
    assert set(paths["/auth/account"]) >= {"get", "patch"}
    assert set(paths["/auth/account/change-password"]["post"]["responses"]) >= {
        "200",
        "403",
        "422",
    }
    assert set(paths["/auth/confirm-email-change"]["post"]["responses"]) >= {
        "200",
        "400",
    }
    assert "/auth/sessions/{session_id}" in paths
    assert "/auth/sessions/revoke-others" in paths
