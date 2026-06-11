"""OpenAI-compatible request and response models for /v1/chat/completions.

These match the OpenAI Chat Completions API shape so any OpenAI client can
talk to this gateway unchanged. The provider layer translates these to/from
each vendor's native format — this shape never leaks into providers.
"""

from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


# ============================================================
# Request
# ============================================================


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model name; used to route to a provider")
    messages: list[ChatMessage] = Field(..., min_length=1)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    stream: bool = Field(default=False)


# ============================================================
# Response
# ============================================================


class ResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class Choice(BaseModel):
    index: int = 0
    message: ResponseMessage
    finish_reason: Literal["stop", "length", "content_filter"] = "stop"


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: Usage

    @classmethod
    def from_completion(
        cls,
        *,
        model: str,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        finish_reason: Literal["stop", "length", "content_filter"] = "stop",
    ) -> ChatCompletionResponse:
        """Build a response from a provider's raw output."""
        return cls(
            model=model,
            choices=[
                Choice(
                    message=ResponseMessage(content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )