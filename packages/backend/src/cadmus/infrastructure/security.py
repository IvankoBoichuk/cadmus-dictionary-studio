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

    def verify(self, password: str, password_hash: str | None) -> bool:
        """Verify a password while doing equivalent work for unknown accounts."""
        if password_hash is None:
            salt = bytes(16)
            expected_hash = bytes(32)
            n, r, p = 2**15, 8, 3
        else:
            try:
                algorithm, n_text, r_text, p_text, salt_text, hash_text = (
                    password_hash.split("$")
                )
                if algorithm != "scrypt":
                    return False
                n, r, p = int(n_text), int(r_text), int(p_text)
                salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
                expected_hash = base64.urlsafe_b64decode(hash_text.encode("ascii"))
            except (ValueError, UnicodeEncodeError):
                return False

        candidate_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected_hash),
            maxmem=64 * 1024 * 1024,
        )
        return secrets.compare_digest(candidate_hash, expected_hash)


class SecureVerificationTokenProvider:
    """Issue high-entropy tokens while persisting only deterministic digests."""

    def issue(self) -> tuple[str, str]:
        raw_token = secrets.token_urlsafe(32)
        return raw_token, self.digest(raw_token)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SecureSessionTokenProvider:
    """Issue opaque session credentials while persisting only their digests."""

    def issue(self) -> tuple[str, str]:
        raw_token = secrets.token_urlsafe(32)
        return raw_token, self.digest(raw_token)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
