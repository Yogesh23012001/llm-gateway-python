"""LLM Gateway — OpenAI-compatible multi-provider gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from gateway.config import get_settings
from gateway.observability.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("gateway_starting", default_model=settings.default_model)
    # Providers, DB pool, router wired in Hours 2-4
    yield
    logger.info("gateway_stopping")


app = FastAPI(title="LLM Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}