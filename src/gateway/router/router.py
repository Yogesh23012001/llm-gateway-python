"""The router: selects a provider by model name, executes with retries.

Routing is by model name via each provider's handles() method. Retries read
error.retryable (set by the provider that caught the vendor exception) — the
router does not classify exceptions itself.
"""

from __future__ import annotations

import asyncio

import structlog

from gateway.providers.base import (
    CompletionRequest,
    CompletionResult,
    LLMProvider,
)
from gateway.providers.errors import ProviderError

logger = structlog.get_logger(__name__)


class NoProviderError(Exception):
    """No registered provider handles the requested model."""


class LLMRouter:
    def __init__(
        self,
        providers: list[LLMProvider],
        *,
        max_retries: int = 3,
        base_backoff_seconds: float = 0.5,
    ) -> None:
        self._providers = providers
        self._max_retries = max_retries
        self._base_backoff = base_backoff_seconds

    def _select(self, model: str) -> LLMProvider:
        for provider in self._providers:
            if provider.handles(model):
                return provider
        raise NoProviderError(f"no provider handles model {model!r}")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        provider = self._select(request.model)

        last_error: ProviderError | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                result = await provider.complete(request)
                if attempt > 1:
                    logger.info(
                        "provider_retry_succeeded",
                        provider=provider.name,
                        attempt=attempt,
                    )
                return result
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    logger.warning(
                        "provider_error_not_retryable",
                        provider=provider.name,
                        error=str(exc)[:200],
                    )
                    raise
                if attempt == self._max_retries:
                    logger.warning(
                        "provider_retries_exhausted",
                        provider=provider.name,
                        attempts=attempt,
                    )
                    raise
                backoff = self._base_backoff * (2 ** (attempt - 1))
                logger.info(
                    "provider_retrying",
                    provider=provider.name,
                    attempt=attempt,
                    backoff_seconds=backoff,
                    error=str(exc)[:120],
                )
                await asyncio.sleep(backoff)

        # Unreachable, but satisfies type checker
        assert last_error is not None
        raise last_error