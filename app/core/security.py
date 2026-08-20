from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 600_000
PASSWORD_SCHEME = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_SCHEME,
            str(PBKDF2_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iteration_text, salt_text, digest_text = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iteration_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
