"""Model → provider routing — implemented in Hour 3."""

from __future__ import annotations

from gateway.providers.base import CompletionRequest, CompletionResult, LLMProvider


class ModelRouter:
    """Resolves a model name to a registered provider and delegates the call."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        # model name (or prefix) -> provider name
        self._model_map: dict[str, str] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    def resolve(self, model: str) -> LLMProvider:
        raise NotImplementedError("Model resolution is implemented in Hour 3.")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        provider = self.resolve(request.model)
        return await provider.complete(request)
