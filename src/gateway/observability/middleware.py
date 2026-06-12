"""Request-ID middleware. Generates a request id at the edge, binds it to the
structlog context for the duration of the request, and returns it as a header.

This is infrastructure metadata — NOT part of the OpenAI API contract. Clients
don't send it; we generate it. It threads through every log line for the request
so you can grep one id and see the whole request lifecycle.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Honor an incoming id (e.g., from an upstream proxy) or generate one
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

        # Bind to structlog contextvars — every log line in this request gets it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Make it available to handlers via request.state
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response