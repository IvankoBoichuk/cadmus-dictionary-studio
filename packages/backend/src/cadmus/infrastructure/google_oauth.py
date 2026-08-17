"""HTTP adapter for Google's OAuth 2.0 / OpenID Connect endpoints.

Uses authlib's httpx integration for the Authorization Code + PKCE exchange
and joserfc for OIDC ID-token verification (issuer, audience, signature,
expiration). ``nonce`` is checked explicitly since token verification alone
does not bind a token to a specific authorization request.
"""

import time

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from joserfc import jwt
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from cadmus.identity import GoogleIdentityClaims, GoogleOAuthError

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_SCOPE = "openid email"


class AuthlibGoogleOAuthClient:
    """``GoogleOAuthClient`` backed by authlib's httpx OAuth2 integration."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_url: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_url = redirect_url
        self._timeout_seconds = timeout_seconds

    def build_authorization_url(
        self, state: str, nonce: str, code_challenge: str
    ) -> str:
        """Build the Google consent-screen URL for a fresh login attempt."""
        client = OAuth2Client(
            client_id=self._client_id,
            redirect_uri=self._redirect_url,
            scope=GOOGLE_SCOPE,
        )
        authorization_url, _ = client.create_authorization_url(
            GOOGLE_AUTHORIZATION_ENDPOINT,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        return str(authorization_url)

    def exchange_code(
        self, code: str, code_verifier: str, expected_nonce: str
    ) -> GoogleIdentityClaims:
        """Exchange an authorization code for a verified set of identity claims."""
        try:
            return self._exchange_code(code, code_verifier, expected_nonce)
        except GoogleOAuthError:
            raise
        except Exception as error:
            raise GoogleOAuthError("failed to verify the Google identity") from error

    def _exchange_code(
        self, code: str, code_verifier: str, expected_nonce: str
    ) -> GoogleIdentityClaims:
        with OAuth2Client(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=self._redirect_url,
            timeout=self._timeout_seconds,
        ) as client:
            token = client.fetch_token(
                GOOGLE_TOKEN_ENDPOINT,
                code=code,
                code_verifier=code_verifier,
            )

        id_token = token.get("id_token")
        if not isinstance(id_token, str):
            raise GoogleOAuthError("Google token response is missing an ID token")

        jwks_response = httpx.get(GOOGLE_JWKS_URI, timeout=self._timeout_seconds)
        jwks_response.raise_for_status()
        key_set = KeySet.import_key_set(jwks_response.json())

        decoded = jwt.decode(id_token, key_set, algorithms=["RS256"])
        claims_registry = JWTClaimsRegistry(
            now=int(time.time()),
            iss={"essential": True, "value": GOOGLE_ISSUER},
            aud={"essential": True, "value": self._client_id},
            exp={"essential": True},
            nonce={"essential": True, "value": expected_nonce},
        )
        claims_registry.validate(decoded.claims)

        return GoogleIdentityClaims(
            subject=str(decoded.claims["sub"]),
            email=str(decoded.claims["email"]),
            email_verified=bool(decoded.claims.get("email_verified", False)),
        )
