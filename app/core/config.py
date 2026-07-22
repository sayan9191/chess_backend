"""
Application settings loaded from environment variables.

Uses pydantic-settings for validation and type coercion.
All secrets and connection strings must be provided via .env file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
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

    # Database (Supabase PostgreSQL)
    database_url: str = Field(
        ...,
        description="Async PostgreSQL connection string (postgresql+asyncpg://...)",
    )
    database_echo: bool = False

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

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_driver(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        from app.utils.database_url import validate_database_url as _validate

        return _validate(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | List[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
