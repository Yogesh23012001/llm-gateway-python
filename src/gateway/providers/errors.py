"""Provider error hierarchy. Vendor exceptions are translated to these at
the provider boundary so the router/API layers never see raw vendor errors."""

from __future__ import annotations


class ProviderError(Exception):
    """Base for all provider failures."""

    def __init__(self, message: str, *, provider: str, retryable: bool) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class ProviderRateLimitError(ProviderError):
    """Vendor returned 429. Retryable."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message, provider=provider, retryable=True)


class ProviderTimeoutError(ProviderError):
    """Vendor call timed out. Retryable."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message, provider=provider, retryable=True)


class ProviderBadRequestError(ProviderError):
    """Vendor rejected the request (4xx, not 429). Not retryable."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message, provider=provider, retryable=False)


class ProviderServerError(ProviderError):
    """Vendor had a 5xx. Retryable."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message, provider=provider, retryable=True)