from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from cadmus.config import Environment, Settings
from cadmus.identity import (
    AccountStatus,
    AuthenticationService,
    GoogleAuthenticationError,
    GoogleAuthenticationService,
    GoogleAuthFailure,
    GoogleLoginChallenge,
    LoginResult,
    RegistrationService,
    User,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

MOCK_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth?mock=1"


@dataclass
class StubGoogleAuthenticationService:
    complete_error: GoogleAuthenticationError | None = None
    challenge: GoogleLoginChallenge = field(
        default_factory=lambda: GoogleLoginChallenge(
            authorization_url=MOCK_AUTHORIZATION_URL,
            state="mock-state",
            nonce="mock-nonce",
            code_verifier="mock-verifier",
        )
    )
    complete_calls: list[dict[str, str]] = field(default_factory=list)

    def start_login(self) -> GoogleLoginChallenge:
        return self.challenge

    def complete_login(
        self,
        *,
        code: str,
        state: str,
        expected_state: str,
        expected_nonce: str,
        code_verifier: str,
    ) -> LoginResult:
        self.complete_calls.append(
            {
                "code": code,
                "state": state,
                "expected_state": expected_state,
                "expected_nonce": expected_nonce,
                "code_verifier": code_verifier,
            }
        )
        if self.complete_error is not None:
            raise self.complete_error
        return LoginResult(user=self._user(), session_token="raw-session-token")

    @staticmethod
    def _user() -> User:
        return User(
            id=UUID("8158fd82-2d50-4f4f-af31-e969bab77163"),
            email="user@example.com",
            password_hash=None,
            status=AccountStatus.ACTIVE,
            created_at=datetime.now(UTC),
            activated_at=datetime.now(UTC),
        )


def client_for(
    google_authentication: StubGoogleAuthenticationService,
    settings: Settings | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            settings=settings,
            database_engine=engine,
            registration_service=cast(RegistrationService, object()),
            authentication_service=cast(AuthenticationService, object()),
            google_authentication_service=cast(
                GoogleAuthenticationService, google_authentication
            ),
        ),
        follow_redirects=False,
    )


def test_start_redirects_to_google_and_sets_oauth_cookies() -> None:
    with client_for(StubGoogleAuthenticationService()) as client:
        response = client.get("/auth/google/start")

    assert response.status_code == 302
    assert response.headers["location"] == MOCK_AUTHORIZATION_URL
    cookies = response.headers.get_list("set-cookie")
    assert any(cookie.startswith("cadmus_g_state=mock-state") for cookie in cookies)
    assert any(cookie.startswith("cadmus_g_nonce=mock-nonce") for cookie in cookies)
    assert any(
        cookie.startswith("cadmus_g_verifier=mock-verifier") for cookie in cookies
    )
    assert all("HttpOnly" in cookie for cookie in cookies)
    assert all("SameSite=lax" in cookie for cookie in cookies)
    assert all("Path=/auth/google" in cookie for cookie in cookies)


def test_start_uses_secure_cookies_in_production() -> None:
    with client_for(
        StubGoogleAuthenticationService(), Settings(environment=Environment.PRODUCTION)
    ) as client:
        response = client.get("/auth/google/start")

    cookies = response.headers.get_list("set-cookie")
    assert all("Secure" in cookie for cookie in cookies)


def test_callback_sets_session_cookie_and_redirects_to_dashboard() -> None:
    service = StubGoogleAuthenticationService()
    with client_for(service) as client:
        client.cookies.set("cadmus_g_state", "mock-state")
        client.cookies.set("cadmus_g_nonce", "mock-nonce")
        client.cookies.set("cadmus_g_verifier", "mock-verifier")
        response = client.get(
            "/auth/google/callback", params={"code": "auth-code", "state": "mock-state"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/dashboard"
    assert service.complete_calls == [
        {
            "code": "auth-code",
            "state": "mock-state",
            "expected_state": "mock-state",
            "expected_nonce": "mock-nonce",
            "code_verifier": "mock-verifier",
        }
    ]
    cookies = response.headers.get_list("set-cookie")
    assert any(
        cookie.startswith("cadmus_session=raw-session-token") for cookie in cookies
    )
    oauth_cookie_names = {"cadmus_g_state", "cadmus_g_nonce", "cadmus_g_verifier"}
    cleared = [c for c in cookies if c.split("=", 1)[0] in oauth_cookie_names]
    assert len(cleared) == 3
    assert all("Max-Age=0" in cookie for cookie in cleared)


def test_callback_redirects_to_login_with_error_when_google_reports_a_failure() -> None:
    with client_for(StubGoogleAuthenticationService()) as client:
        response = client.get(
            "/auth/google/callback", params={"error": "access_denied"}
        )

    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == (
        "http://localhost:5173/login"
    )
    assert parse_qs(location.query) == {"error": ["google_auth_failed"]}
    cookies = response.headers.get_list("set-cookie")
    assert not any(cookie.startswith("cadmus_session=") for cookie in cookies)


def test_callback_redirects_to_login_with_error_when_oauth_cookies_are_missing() -> (
    None
):
    with client_for(StubGoogleAuthenticationService()) as client:
        response = client.get(
            "/auth/google/callback", params={"code": "auth-code", "state": "mock-state"}
        )

    assert response.status_code == 302
    assert (
        response.headers["location"]
        == "http://localhost:5173/login?error=google_auth_failed"
    )


def test_callback_redirects_to_login_with_error_when_the_service_rejects_it() -> None:
    service = StubGoogleAuthenticationService(
        complete_error=GoogleAuthenticationError(GoogleAuthFailure.INVALID_STATE)
    )
    with client_for(service) as client:
        client.cookies.set("cadmus_g_state", "mock-state")
        client.cookies.set("cadmus_g_nonce", "mock-nonce")
        client.cookies.set("cadmus_g_verifier", "mock-verifier")
        response = client.get(
            "/auth/google/callback", params={"code": "auth-code", "state": "mock-state"}
        )

    assert response.status_code == 302
    assert (
        response.headers["location"]
        == "http://localhost:5173/login?error=google_auth_failed"
    )
    cookies = response.headers.get_list("set-cookie")
    assert not any(cookie.startswith("cadmus_session=") for cookie in cookies)


def test_openapi_documents_google_oauth_routes() -> None:
    with client_for(StubGoogleAuthenticationService()) as client:
        schema = client.get("/openapi.json").json()

    assert "/auth/google/start" in schema["paths"]
    assert "/auth/google/callback" in schema["paths"]


def test_google_routes_are_absent_when_not_configured() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    app = create_app(
        settings=Settings(
            google_oauth_client_id=None,
            google_oauth_client_secret=None,
            google_oauth_redirect_url=None,
        ),
        database_engine=engine,
        registration_service=cast(RegistrationService, object()),
        authentication_service=cast(AuthenticationService, object()),
    )
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/auth/google/start")

    assert response.status_code == 404
