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


from gateway.router.circuit_breaker import CircuitBreaker, CircuitOpenError


class LLMRouter:
    def __init__(
        self,
        providers: list[LLMProvider],
        *,
        max_retries: int = 3,
        base_backoff_seconds: float = 0.5,
        breaker_threshold: int = 5,
        breaker_cooldown: float = 30.0,
    ) -> None:
        self._providers = providers
        self._max_retries = max_retries
        self._base_backoff = base_backoff_seconds
        # One breaker per provider, keyed by name
        self._breakers: dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(p.name, failure_threshold=breaker_threshold, cooldown_seconds=breaker_cooldown)
            for p in providers
        }

    def _select(self, model: str) -> LLMProvider:
        for provider in self._providers:
            if provider.handles(model):
                return provider
        raise NoProviderError(f"no provider handles model {model!r}")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        provider = self._select(request.model)
        breaker = self._breakers[provider.name]

        # Fail fast if the breaker is open
        if not breaker.allow_request():
            logger.warning("request_rejected_circuit_open", provider=provider.name)
            raise CircuitOpenError(provider.name)

        last_error: ProviderError | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                result = await provider.complete(request)
                breaker.record_success()    # ← report success
                if attempt > 1:
                    logger.info("provider_retry_succeeded", provider=provider.name, attempt=attempt)
                return result
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    breaker.record_failure()    # ← non-retryable counts as a failure
                    raise
                if attempt == self._max_retries:
                    breaker.record_failure()    # ← exhausted retries = a failure
                    logger.warning("provider_retries_exhausted", provider=provider.name, attempts=attempt)
                    raise
                backoff = self._base_backoff * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

        breaker.record_failure()
        assert last_error is not None
        raise last_error