"""Standard-library credential security adapters."""

import base64
import hashlib
import secrets


class ScryptPasswordHasher:
    """Hash passwords with a random salt and memory-hard scrypt."""

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        password_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**15,
            r=8,
            p=3,
            dklen=32,
            maxmem=64 * 1024 * 1024,
        )
        encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
        encoded_hash = base64.urlsafe_b64encode(password_hash).decode("ascii")
        return f"scrypt$32768$8$3${encoded_salt}${encoded_hash}"


class SecureVerificationTokenProvider:
    """Issue high-entropy tokens while persisting only deterministic digests."""

    def issue(self) -> tuple[str, str]:
        raw_token = secrets.token_urlsafe(32)
        return raw_token, self.digest(raw_token)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
