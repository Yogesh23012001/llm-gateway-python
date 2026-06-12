"""The LLMProvider protocol and shared provider types.

A provider's only job: take normalized messages, call a vendor API, return
a normalized CompletionResult. Providers know their vendor's shape. They do
NOT know the OpenAI envelope — that translation happens in the API layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


# ============================================================
# Normalized types — the gateway's internal vocabulary
# ============================================================


@dataclass(frozen=True)
class ProviderMessage:
    """A message in the gateway's normalized form (provider-agnostic)."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class CompletionResult:
    """What every provider returns. Primitives only — no OpenAI envelope.

    The API layer wraps this into a ChatCompletionResponse via from_completion.
    """

    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: Literal["stop", "length", "content_filter"]
    # Which provider produced this ("anthropic", "gemini") — set by the provider,
    # so callers don't need a model->provider reverse lookup.
    provider: str
    # The provider's own model id, for logging/verification
    model: str


@dataclass(frozen=True)
class CompletionRequest:
    """What every provider receives. Normalized, provider-agnostic."""

    messages: list[ProviderMessage]
    model: str
    max_tokens: int | None
    temperature: float | None


# ============================================================
# The protocol
# ============================================================


@runtime_checkable
class LLMProvider(Protocol):
    """Every provider implements this. One method that matters."""

    name: str  # "anthropic", "gemini" — for logging and routing

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Call the vendor API and return a normalized result.

        Raises a ProviderError subclass on failure (never a raw vendor exception).
        """
        ...