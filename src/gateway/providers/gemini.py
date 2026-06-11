"""Gemini provider — translates the gateway's normalized request to the
google-genai API and back."""

from __future__ import annotations

import structlog
from google import genai
from google.genai import types as gtypes
from google.genai import errors as gerrors

from gateway.providers.base import CompletionRequest, CompletionResult
from gateway.providers.errors import (
    ProviderBadRequestError,
    ProviderRateLimitError,
    ProviderServerError,
)

logger = structlog.get_logger(__name__)


_MODEL_MAP = {
    "gemini-flash": "gemini-2.0-flash",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "gemini-2.5-pro": "gemini-2.5-pro",
}


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def handles(self, model: str) -> bool:
        return model in _MODEL_MAP or model.startswith("gemini")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        api_model = _MODEL_MAP.get(request.model, request.model)

        # Gemini: system goes in config.system_instruction, not contents.
        system_text = "\n\n".join(
            m.content for m in request.messages if m.role == "system"
        )
        # Gemini uses "model" for assistant role, and a contents list.
        contents = []
        for m in request.messages:
            if m.role == "system":
                continue
            gemini_role = "model" if m.role == "assistant" else "user"
            contents.append(
                gtypes.Content(role=gemini_role, parts=[gtypes.Part(text=m.content)])
            )

        config_kwargs: dict = {}
        if system_text:
            config_kwargs["system_instruction"] = system_text
        if request.max_tokens is not None:
            config_kwargs["max_output_tokens"] = request.max_tokens
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature

        try:
            response = await self._client.aio.models.generate_content(
                model=api_model,
                contents=contents,
                config=gtypes.GenerateContentConfig(**config_kwargs),
            )
        except gerrors.APIError as exc:
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status == 429:
                raise ProviderRateLimitError(str(exc), provider=self.name) from exc
            if status and status >= 500:
                raise ProviderServerError(str(exc), provider=self.name) from exc
            raise ProviderBadRequestError(str(exc), provider=self.name) from exc

        text = response.text or ""
        candidate = response.candidates[0] if response.candidates else None
        finish_reason = _translate_finish_reason(
            getattr(candidate, "finish_reason", None)
        )

        usage = response.usage_metadata
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        # Gemini 2.5 "thinking" tokens are billed as output but reported separately
        # from candidates_token_count — count both, or output cost is undercounted.
        completion_tokens = (getattr(usage, "candidates_token_count", 0) or 0) + (
            getattr(usage, "thoughts_token_count", 0) or 0
        )

        return CompletionResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
            model=api_model,
        )


def _translate_finish_reason(reason: object) -> str:
    """Map Gemini finish reasons to the gateway's finish_reason vocabulary."""
    name = getattr(reason, "name", None) or str(reason or "")
    if name == "MAX_TOKENS":
        return "length"
    if name in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        return "content_filter"
    return "stop"