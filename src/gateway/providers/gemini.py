"""Google Gemini provider adapter — implemented in Hour 2."""

from __future__ import annotations

from gateway.providers.base import CompletionRequest, CompletionResponse


class GeminiProvider:
    """Maps the gateway's normalized types to the Google Gen AI API."""

    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Hour 2: self._client = genai.Client(api_key=api_key)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError("GeminiProvider is implemented in Hour 2.")
