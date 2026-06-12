"""Gateway configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the project root, not the process's cwd, so the app
# loads the same credentials no matter what directory uvicorn is launched from.
# src/gateway/config.py -> parents[2] is the project root.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider credentials
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://gateway:gateway@localhost:5435/gateway"
    )

    # Service
    log_level: str = Field(default="INFO")
    request_timeout_seconds: float = Field(default=60.0)

    # Default model if the request doesn't specify a routable one
    default_model: str = Field(default="claude-haiku-4-5-20251001")


@lru_cache
def get_settings() -> Settings:
    return Settings()