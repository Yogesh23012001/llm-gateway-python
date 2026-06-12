"""The /v1/chat/completions endpoint. Translates OpenAI shape <-> normalized
shape, delegates to the router."""

from __future__ import annotations
from gateway.router.circuit_breaker import CircuitOpenError

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


import time

from gateway.persistence.cost_log import record_completion
from gateway.persistence.pricing import calculate_cost_usd


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
) -> ChatCompletionResponse:
    llm_router: LLMRouter = request.app.state.router
    session_factory = request.app.state.session_factory
    request_id = getattr(request.state, "request_id", "")

    if payload.stream:
        raise HTTPException(status_code=400, detail={"error": "streaming not yet supported"})

    normalized = _to_normalized(payload)
    start = time.perf_counter()

    try:
        result = await llm_router.complete(normalized)
    except NoProviderError as exc:
        raise HTTPException(status_code=400, detail={"error": "unsupported_model", "message": str(exc)}) from exc
    except ProviderError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        # Record the failed attempt too — you want error-rate visibility
        await record_completion(
            session_factory,
            request_id=request_id,
            requested_model=payload.model,
            resolved_model=payload.model,
            provider=exc.provider,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            latency_ms=latency_ms,
            outcome="error",
        )
        status = 503 if exc.retryable else 502
        raise HTTPException(status_code=status, detail={"error": "provider_error", "provider": exc.provider}) from exc
    except CircuitOpenError as exc:
        logger.warning("completion_rejected_circuit_open", provider=exc.provider, request_id=request_id)
        raise HTTPException(
            status_code=503,
            detail={"error": "provider_unavailable", "provider": exc.provider, "reason": "circuit_open"},
            headers={"Retry-After": "30"},
        ) from exc

    latency_ms = (time.perf_counter() - start) * 1000
    cost = calculate_cost_usd(
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

    await record_completion(
        session_factory,
        request_id=request_id,
        requested_model=payload.model,
        resolved_model=result.model,
        provider=result.provider,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
        outcome="success",
    )

    logger.info(
        "completion_success",
        requested_model=payload.model,
        resolved_model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cost_usd=cost,
        latency_ms=round(latency_ms, 1),
    )

    return ChatCompletionResponse.from_completion(
        model=payload.model,
        content=result.text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        finish_reason=result.finish_reason,
    )