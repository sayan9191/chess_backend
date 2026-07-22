"""Security utilities: JWT creation/verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError, PyJWTError

from app.core.config import get_settings


def create_access_token(
    subject: str | UUID,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT using the project JWT secret."""
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise ValueError("Supabase JWT secret is not configured")
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def is_token_expired_error(exc: PyJWTError) -> bool:
    return isinstance(exc, jwt.ExpiredSignatureError) or "expired" in str(exc).lower()


# Alias for backward compatibility in dependencies
JWTError = InvalidTokenError
