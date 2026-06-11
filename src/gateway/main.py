"""LLM Gateway — OpenAI-compatible multi-provider gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from gateway.config import get_settings
from gateway.observability.logging import configure_logging

logger = structlog.get_logger(__name__)

from gateway.providers.anthropic import AnthropicProvider
from gateway.providers.gemini import GeminiProvider
from gateway.router.router import LLMRouter
from gateway.api.routes import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    providers = []
    if settings.anthropic_api_key:
        providers.append(AnthropicProvider(settings.anthropic_api_key, timeout=settings.request_timeout_seconds))
    if settings.gemini_api_key:
        providers.append(GeminiProvider(settings.gemini_api_key))

    app.state.router = LLMRouter(providers)
    logger.info("gateway_starting", providers=[p.name for p in providers])
    yield
    logger.info("gateway_stopping")


app = FastAPI(title="LLM Gateway", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}