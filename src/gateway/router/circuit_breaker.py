"""Per-provider circuit breaker.

States: CLOSED (normal) -> OPEN (failing, reject fast) -> HALF_OPEN (probing)
-> CLOSED (recovered) or back to OPEN (still failing).

Trips after `failure_threshold` consecutive failures. Stays OPEN for
`cooldown_seconds`, then allows one probe (HALF_OPEN). Probe success closes
the breaker; probe failure reopens it.

This composes with retries: retries handle blips within a single call, the
breaker handles sustained provider outages across calls.
"""

from __future__ import annotations

import time
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the breaker is OPEN."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"circuit open for provider {provider!r}")
        self.provider = provider


class CircuitBreaker:
    def __init__(
        self,
        provider: str,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self._provider = provider
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown_seconds

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow_request(self) -> bool:
        """Check before calling the provider. Updates state on cooldown expiry.

        Returns True if the request may proceed, False if it should be rejected.
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Has the cooldown elapsed? If so, move to HALF_OPEN and allow a probe.
            if self._opened_at is not None and (time.monotonic() - self._opened_at) >= self._cooldown:
                self._state = CircuitState.HALF_OPEN
                logger.info("circuit_half_open", provider=self._provider)
                return True
            return False

        # HALF_OPEN: allow the single probe (the caller is the probe)
        return True

    def record_success(self) -> None:
        """Call after a successful provider response."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("circuit_closed_after_recovery", provider=self._provider)
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        """Call after a provider failure."""
        self._consecutive_failures += 1

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed — reopen
            self._trip()
            return

        if self._consecutive_failures >= self._failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.warning(
            "circuit_opened",
            provider=self._provider,
            consecutive_failures=self._consecutive_failures,
            cooldown_seconds=self._cooldown,
        )