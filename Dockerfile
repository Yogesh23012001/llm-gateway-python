# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Compile to .pyc for faster cold starts; copy into the layer (no cross-fs hardlinks)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1) Dependencies only — cached until pyproject.toml / uv.lock change.
#    --no-install-project: the app source isn't in the image yet, so don't try to
#    build the gateway package here (that would fail — src/ isn't copied).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) Copy source, then install the project itself.
#    README.md is referenced by pyproject (readme = "README.md") at build time.
COPY README.md ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Drop root for runtime
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

# Use the synced venv directly — no `uv run` overhead at container start
ENV PATH="/app/.venv/bin:$PATH"

# Render (and most PaaS) inject $PORT; default to 8080 for local runs
ENV PORT=8080
EXPOSE 8080

# Shell form so ${PORT} is expanded at runtime
CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT}"]
