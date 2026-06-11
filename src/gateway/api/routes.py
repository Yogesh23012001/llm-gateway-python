"""OpenAI-compatible HTTP routes."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from gateway.api.models import ChatCompletionRequest, ChatCompletionResponse

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    body: ChatCompletionRequest, request: Request
) -> ChatCompletionResponse:
    """Accept an OpenAI-format chat request and route it to a provider.

    The contract is defined now; Hour 3 wires this to the ModelRouter
    (`request.app.state.router`). Until then we advertise the shape and
    return 501.
    """
    log.info(
        "chat.completions.request",
        model=body.model,
        messages=len(body.messages),
        stream=body.stream,
    )

    # Hour 3:
    #   router = request.app.state.router
    #   return await router.complete(body)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model routing is implemented in Hour 3.",
    )
