"""Thin HTTP adapter for the Google OAuth login use case."""

from datetime import timedelta

from cadmus.identity import GoogleAuthenticationError, GoogleAuthenticationService
from fastapi import APIRouter, Cookie
from fastapi.responses import RedirectResponse

from cadmus_api.routes.auth import set_session_cookie

STATE_COOKIE_NAME = "cadmus_g_state"
NONCE_COOKIE_NAME = "cadmus_g_nonce"
VERIFIER_COOKIE_NAME = "cadmus_g_verifier"
# Must match the browser-visible path, not this router's own prefix: nginx's
# web container strips "/api" before forwarding here, so a cookie scoped to
# "/auth/google" would never come back on a request to "/api/auth/google/*".
OAUTH_COOKIE_PATH = "/api/auth/google"
OAUTH_COOKIE_MAX_AGE_SECONDS = 600
LOGIN_FAILURE_REDIRECT_QUERY = "?error=google_auth_failed"


def create_google_oauth_router(
    google_authentication: GoogleAuthenticationService,
    session_lifetime: timedelta,
    secure_cookie: bool,
    public_web_url: str,
) -> APIRouter:
    """Create Google OAuth routes bound to the application use case."""
    router = APIRouter(prefix="/auth/google", tags=["identity"])
    frontend_base_url = public_web_url.rstrip("/")

    def _set_oauth_cookie(response: RedirectResponse, name: str, value: str) -> None:
        response.set_cookie(
            key=name,
            value=value,
            max_age=OAUTH_COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path=OAUTH_COOKIE_PATH,
        )

    def _clear_oauth_cookies(response: RedirectResponse) -> None:
        for name in (STATE_COOKIE_NAME, NONCE_COOKIE_NAME, VERIFIER_COOKIE_NAME):
            response.delete_cookie(name, path=OAUTH_COOKIE_PATH)

    @router.get("/start", summary="Redirect the browser to Google's consent screen")
    def start() -> RedirectResponse:
        challenge = google_authentication.start_login()
        response = RedirectResponse(challenge.authorization_url, status_code=302)
        _set_oauth_cookie(response, STATE_COOKIE_NAME, challenge.state)
        _set_oauth_cookie(response, NONCE_COOKIE_NAME, challenge.nonce)
        _set_oauth_cookie(response, VERIFIER_COOKIE_NAME, challenge.code_verifier)
        return response

    @router.get(
        "/callback", summary="Resolve Google's callback into an authenticated session"
    )
    def callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        oauth_state: str | None = Cookie(default=None, alias=STATE_COOKIE_NAME),
        oauth_nonce: str | None = Cookie(default=None, alias=NONCE_COOKIE_NAME),
        oauth_verifier: str | None = Cookie(default=None, alias=VERIFIER_COOKIE_NAME),
    ) -> RedirectResponse:
        response = _failure_response()
        if (
            error is None
            and code is not None
            and state is not None
            and oauth_state is not None
            and oauth_nonce is not None
            and oauth_verifier is not None
        ):
            try:
                result = google_authentication.complete_login(
                    code=code,
                    state=state,
                    expected_state=oauth_state,
                    expected_nonce=oauth_nonce,
                    code_verifier=oauth_verifier,
                )
            except GoogleAuthenticationError:
                response = _failure_response()
            else:
                response = RedirectResponse(
                    f"{frontend_base_url}/dashboard", status_code=302
                )
                set_session_cookie(
                    response, result.session_token, session_lifetime, secure_cookie
                )
        _clear_oauth_cookies(response)
        return response

    def _failure_response() -> RedirectResponse:
        return RedirectResponse(
            f"{frontend_base_url}/login{LOGIN_FAILURE_REDIRECT_QUERY}",
            status_code=302,
        )

    return router
