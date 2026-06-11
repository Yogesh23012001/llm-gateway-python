# LLM Gateway

An OpenAI-compatible gateway that routes `/v1/chat/completions` requests to
multiple upstream LLM providers (Anthropic Claude, Google Gemini), with model
routing, cost tracking, and structured logging.

## Status (build plan)

| Hour | Area | Files |
| ---- | ---- | ----- |
| 1 | API surface + app skeleton | `main.py`, `config.py`, `api/`, `providers/base.py`, `observability/logging.py` |
| 2 | Provider adapters | `providers/anthropic.py`, `providers/gemini.py` |
| 3 | Model → provider routing | `router/router.py` |
| 4 | Postgres cost tracking | `persistence/cost_log.py` |

## Layout

```
src/gateway/
├── main.py              # FastAPI app + lifespan
├── config.py            # Settings (pydantic-settings)
├── api/
│   ├── models.py        # OpenAI-compatible request/response models
│   └── routes.py        # /v1/chat/completions endpoint
├── providers/
│   ├── base.py          # LLMProvider protocol + normalized types
│   ├── anthropic.py     # Hour 2
│   └── gemini.py        # Hour 2
├── router/router.py     # Hour 3 — routes model → provider
├── persistence/cost_log.py  # Hour 4 — Postgres cost tracking
└── observability/logging.py # structlog setup
```

## Getting started

```bash
# Install dependencies (uv)
uv sync

# Configure environment
cp .env.example .env   # then fill in API keys

# Start Postgres (for Hour 4)
docker compose up -d

# Run the API
uv run uvicorn gateway.main:app --reload

# Health check
curl http://localhost:8000/healthz
```

> `/v1/chat/completions` returns `501 Not Implemented` until the router and
> providers are wired up (Hours 2–3).

## Development

```bash
uv run pytest        # tests
uv run ruff check .  # lint
uv run mypy src      # type-check
```
