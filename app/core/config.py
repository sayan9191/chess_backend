"""
Application settings loaded from environment variables.

Uses pydantic-settings for validation and type coercion.
All secrets and connection strings must be provided via .env file.

Database connection — choose ONE approach:
  1. Split vars (recommended on Vercel): DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT
  2. Single URL: DATABASE_URL (password must be URL-encoded if it contains @ # etc.)
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Chess Backend API"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database — option A: single URL
    database_url: str | None = Field(
        default=None,
        description="Async PostgreSQL URL (postgresql+asyncpg://...). Password must be URL-encoded.",
    )
    database_echo: bool = False

    # Database — option B: split vars (recommended for Vercel / special characters in password)
    db_host: str = Field(default="", description="e.g. db.xxxx.supabase.co")
    db_user: str = Field(default="", description="e.g. postgres or postgres.xxxx")
    db_password: str = Field(default="", description="Raw password — not URL-encoded")
    db_name: str = Field(default="postgres")
    db_port: int = Field(default=5432, ge=1, le=65535)

    # JWT / Auth
    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Supabase (optional JWT verification)
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_anon_key: str = ""

    # CORS (comma-separated in .env)
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Stockfish
    stockfish_path: str = "stockfish"
    stockfish_skill_level: int = Field(default=10, ge=0, le=20)
    stockfish_move_time_ms: int = Field(default=500, ge=100)

    # Game session / clock
    default_time_limit_seconds: int = Field(default=600, ge=60, le=7200)
    game_idle_timeout_minutes: int = Field(default=30, ge=5, le=1440)

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sync_database_url(self) -> str:
        """Sync driver URL for Alembic migrations."""
        if not self.database_url:
            raise ValueError("database_url is not configured")
        return self.database_url.replace("+asyncpg", "+psycopg")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | List[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @model_validator(mode="after")
    def resolve_database_url(self) -> Settings:
        from app.utils.database_url import build_database_url, validate_database_url

        # Split vars take priority — avoids Vercel URL-encoding issues
        if self.db_host and self.db_user and self.db_password:
            self.database_url = build_database_url(
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                async_driver=True,
            )
            return self

        if self.database_url:
            self.database_url = validate_database_url(self.database_url)
            return self

        raise ValueError(
            "Database not configured. Set either:\n"
            "  • DB_HOST, DB_USER, DB_PASSWORD (and optionally DB_NAME, DB_PORT), or\n"
            "  • DATABASE_URL with a URL-encoded password"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
