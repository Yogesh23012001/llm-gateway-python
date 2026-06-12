"""Anthropic provider — translates the gateway's normalized request to the
Anthropic Messages API and back."""

from __future__ import annotations

import anthropic
import structlog

from gateway.providers.base import (
    CompletionRequest,
    CompletionResult,
)
from gateway.providers.errors import (
    ProviderBadRequestError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)

logger = structlog.get_logger(__name__)


# Map gateway-facing model names to Anthropic's API model ids.
# The gateway accepts friendly names; this is where they resolve.
_MODEL_MAP = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5": "claude-sonnet-4-5",
}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, *, timeout: float = 60.0) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)

    def handles(self, model: str) -> bool:
        """Does this provider serve the given model name?"""
        return model in _MODEL_MAP or model.startswith("claude")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        api_model = _MODEL_MAP.get(request.model, request.model)

        # Anthropic takes system as a top-level param, not a message.
        system_text = "\n\n".join(
            m.content for m in request.messages if m.role == "system"
        )
        chat_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]

        kwargs: dict = {
            "model": api_model,
            "messages": chat_messages,
            "max_tokens": request.max_tokens or 1024,
        }
        if system_text:
            kwargs["system"] = system_text
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.RateLimitError as exc:
            raise ProviderRateLimitError(str(exc), provider=self.name) from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc), provider=self.name) from exc
        except anthropic.BadRequestError as exc:
            raise ProviderBadRequestError(str(exc), provider=self.name) from exc
        except anthropic.APIStatusError as exc:
            # 5xx and other status errors
            if exc.status_code >= 500:
                raise ProviderServerError(str(exc), provider=self.name) from exc
            raise ProviderBadRequestError(str(exc), provider=self.name) from exc

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        finish_reason = _translate_stop_reason(response.stop_reason)

        return CompletionResult(
            text=text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            finish_reason=finish_reason,
            provider=self.name,
            model=api_model,
        )


def _translate_stop_reason(reason: str | None) -> str:
    """Map Anthropic stop reasons to the gateway's finish_reason vocabulary."""
    if reason == "max_tokens":
        return "length"
    if reason in ("end_turn", "stop_sequence", "tool_use"):
        return "stop"
    return "stop"