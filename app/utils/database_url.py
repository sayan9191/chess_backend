"""Database URL parsing, building, and validation helpers."""

from __future__ import annotations

from urllib.parse import quote, urlparse


def build_database_url(
    *,
    user: str,
    password: str,
    host: str,
    port: int = 5432,
    database: str = "postgres",
    async_driver: bool = True,
) -> str:
    """Build a PostgreSQL URL with proper password encoding (safe for @, #, etc.)."""
    scheme = "postgresql+asyncpg" if async_driver else "postgresql+psycopg"
    safe_user = quote(user, safe="")
    safe_password = quote(password, safe="")
    return f"{scheme}://{safe_user}:{safe_password}@{host}:{port}/{database}"


def validate_database_url(url: str) -> str:
    """
    Validate PostgreSQL connection URL and raise a clear error if malformed.

    Prefer DB_HOST + DB_USER + DB_PASSWORD on Vercel instead of a single URL when
    the password contains @, #, or other special characters.
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
        raise ValueError(_malformed_password_hint(None))

    invalid_host_markers = ("@", "#", " ")
    for marker in invalid_host_markers:
        if marker in hostname:
            raise ValueError(_malformed_password_hint(hostname))

    if hostname[0] in "#%0123456789":
        raise ValueError(_malformed_password_hint(hostname))

    return url


def _malformed_password_hint(bad_hostname: str | None) -> str:
    host_part = f" ({bad_hostname!r})" if bad_hostname else ""
    return (
        "DATABASE_URL is invalid"
        + host_part
        + ". Passwords with @ or # break single-line URLs.\n\n"
        "On Vercel, use separate variables instead (no encoding needed):\n"
        "  DB_HOST=db.xxxx.supabase.co\n"
        "  DB_USER=postgres\n"
        "  DB_PASSWORD=your-raw-password\n"
        "  DB_NAME=postgres\n"
        "  DB_PORT=5432\n\n"
        "Or URL-encode the password in DATABASE_URL: @ → %40, # → %23"
    )


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
