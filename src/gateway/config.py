"""Gateway configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider credentials
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://gateway:gateway@localhost:5433/gateway"
    )

    # Service
    log_level: str = Field(default="INFO")
    request_timeout_seconds: float = Field(default=60.0)

    # Default model if the request doesn't specify a routable one
    default_model: str = Field(default="claude-haiku-4-5-20251001")


@lru_cache
def get_settings() -> Settings:
    return Settings()