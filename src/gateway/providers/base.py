"""Provider abstraction: the LLMProvider protocol and the normalized types
that flow between the router and every provider adapter.

Keeping an internal, provider-neutral request/response (instead of passing the
OpenAI wire models straight through) means a new provider only has to map to
these types, and the cost/usage accounting has one shape to reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class Message:
    role: str
    content: str


@dataclass(slots=True)
class CompletionRequest:
    model: str
    messages: list[Message]
    temperature: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None
    # Provider-specific passthrough knobs that don't fit the common shape.
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class CompletionResponse:
    provider: str
    model: str
    content: str
    usage: Usage
    finish_reason: str = "stop"


@runtime_checkable
class LLMProvider(Protocol):
    """Implemented by each provider adapter (Anthropic, Gemini, ...)."""

    name: str

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request upstream and return a normalized response."""
        ...
