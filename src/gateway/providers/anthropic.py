"""Anthropic (Claude) provider adapter — implemented in Hour 2."""

from __future__ import annotations

from gateway.providers.base import CompletionRequest, CompletionResponse


class AnthropicProvider:
    """Maps the gateway's normalized types to the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Hour 2: self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError("AnthropicProvider is implemented in Hour 2.")
