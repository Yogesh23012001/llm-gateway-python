"""The /v1/chat/completions endpoint. Translates OpenAI shape <-> normalized
shape, delegates to the router."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request

from gateway.api.models import ChatCompletionRequest, ChatCompletionResponse
from gateway.providers.base import CompletionRequest, ProviderMessage
from gateway.providers.errors import ProviderError
from gateway.router.router import LLMRouter, NoProviderError

logger = structlog.get_logger(__name__)

router = APIRouter()


def _to_normalized(payload: ChatCompletionRequest) -> CompletionRequest:
    """OpenAI request -> gateway's normalized request."""
    return CompletionRequest(
        messages=[
            ProviderMessage(role=m.role, content=m.content) for m in payload.messages
        ],
        model=payload.model,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
) -> ChatCompletionResponse:
    llm_router: LLMRouter = request.app.state.router

    if payload.stream:
        # Streaming deferred — return a clear error rather than silently ignoring.
        raise HTTPException(
            status_code=400,
            detail={"error": "streaming not yet supported", "param": "stream"},
        )

    normalized = _to_normalized(payload)

    try:
        result = await llm_router.complete(normalized)
    except NoProviderError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_model", "message": str(exc)},
        ) from exc
    except ProviderError as exc:
        # Upstream failed after retries
        status = 503 if exc.retryable else 502
        logger.warning(
            "completion_failed",
            provider=exc.provider,
            retryable=exc.retryable,
            error=str(exc)[:200],
        )
        raise HTTPException(
            status_code=status,
            detail={"error": "provider_error", "provider": exc.provider},
        ) from exc

    return ChatCompletionResponse.from_completion(
        model=payload.model,  # echo the name the client asked for
        content=result.text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        finish_reason=result.finish_reason,
    )