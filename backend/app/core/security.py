"""
Security primitives — JWT + password hashing.

Uses `bcrypt` directly (not passlib — passlib is unmaintained and breaks
on bcrypt>=4.1). Direct bcrypt is simpler and future-proof.

Never stores plaintext passwords.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from backend.app.config import settings


# bcrypt truncates to 72 bytes — pre-hash long passwords or reject.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt. Returns the hash as a UTF-8 string."""
    raw = plain.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Password exceeds {_BCRYPT_MAX_BYTES} bytes (bcrypt limit)")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash. Returns False on any error.

    Validates hash format BEFORE calling bcrypt.checkpw() — the underlying
    Rust binding panics on malformed hashes (rather than raising a normal
    exception), which crashes the pytest session.
    """
    # Basic format validation: bcrypt hashes start with $2a$ / $2b$ / $2y$ and are 59-60 chars
    if not hashed or not hashed.startswith(("$2a$", "$2b$", "$2y$")):
        return False
    if len(hashed) < 59 or len(hashed) > 60:
        return False

    try:
        raw = plain.encode("utf-8")
        if len(raw) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(raw, hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    subject: str,
    roles: list[str] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Create a JWT for the given subject (usually user.business_id)."""
    exp_min = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_min)).timestamp()),
        "roles": roles or [],
        "iss": "leadflow",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])