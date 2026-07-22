"""Database URL parsing and validation helpers."""

from __future__ import annotations

from urllib.parse import quote, unquote, urlparse


def validate_database_url(url: str) -> str:
    """
    Validate PostgreSQL connection URL and raise a clear error if malformed.

    Common mistake: password contains @ or # without URL-encoding, which makes
    the parser treat part of the password as the hostname.
    """
    normalized = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    parsed = urlparse(normalized)

    if parsed.scheme not in ("postgresql", "postgres"):
        raise ValueError(
            f"DATABASE_URL must use postgresql:// or postgresql+asyncpg:// scheme, got {parsed.scheme!r}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(
            "DATABASE_URL is missing a hostname. Check the format: "
            "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE"
        )

    invalid_host_markers = ("@", "#", " ")
    for marker in invalid_host_markers:
        if marker in hostname:
            raise ValueError(_malformed_password_hint(hostname))

    # Hostname starting with digit/punctuation often means password leaked into host
    if hostname[0] in "#%0123456789":
        raise ValueError(_malformed_password_hint(hostname))

    return url


def _malformed_password_hint(bad_hostname: str) -> str:
    return (
        "DATABASE_URL appears malformed — the hostname looks wrong "
        f"({bad_hostname!r}). If your Supabase/Postgres password contains "
        "special characters (@, #, /, :, etc.), you must URL-encode them before "
        "setting DATABASE_URL in Vercel:\n"
        "  @  →  %40\n"
        "  #  →  %23\n"
        "  /  →  %2F\n"
        "Example: password 'Bokachoda@#2001' → 'Bokachoda%40%232001'\n"
        "Full example:\n"
        "  postgresql+asyncpg://postgres:YOUR_ENCODED_PASSWORD@db.xxxx.supabase.co:5432/postgres\n"
        "Tip: In Supabase Dashboard → Project Settings → Database → Connection string, "
        "use the URI tab and copy the string (password is usually pre-encoded)."
    )


def encode_password_for_url(password: str) -> str:
    """URL-encode a database password for use in DATABASE_URL."""
    return quote(password, safe="")


def mask_database_url(url: str) -> str:
    """Return URL with password redacted for logs."""
    normalized = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    parsed = urlparse(normalized)
    if not parsed.username:
        return url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.username}:****@{host}{port}{parsed.path or ''}"
