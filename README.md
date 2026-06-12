# LLM Gateway

An OpenAI-compatible, multi-provider LLM gateway. Point any OpenAI client at it
and route to Anthropic or Gemini by model name — with cost tracking, retries,
and per-provider circuit breaking.

**Live demo:** https://llm-gateway-python.onrender.com

## What it does

Most applications are written against the OpenAI API and effectively locked to a
single vendor. This gateway puts an OpenAI-compatible `/v1/chat/completions`
endpoint in front of multiple providers, so any app already using the OpenAI SDK
can switch to Claude or Gemini — or route across both — by changing **one line**:
the `base_url`. Models are selected by name (`claude-haiku-4-5`, `gemini-flash`),
translated to each vendor's native API, and every call is metered to Postgres
with tokens, cost, and latency. The result is vendor independence and cost
optimization without touching application code.

## Quick start

```python
from openai import OpenAI

# Point the official OpenAI SDK at the gateway
client = OpenAI(base_url="https://llm-gateway-python.onrender.com/v1", api_key="not-needed")

# Route to Claude
client.chat.completions.create(
    model="claude-haiku-4-5",
    messages=[{"role": "user", "content": "Hello"}],
)

# Route to Gemini — same code, one string changed
client.chat.completions.create(
    model="gemini-flash",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Architecture

The gateway is three layers with a deliberately sharp boundary between them: the
**API layer** speaks only the OpenAI wire format, the **provider layer** speaks
only each vendor's native API, and a small **normalized request/result** type
sits in between. The OpenAI envelope never leaks into a provider, and no vendor's
response shape ever leaks back into the API — translation happens exactly once on
each side. The **router** sits in the middle: it selects a provider by model name
and owns resilience (retries for transient failures, a per-provider circuit
breaker for sustained outages). Cost tracking hangs off the response path as a
best-effort write that can never fail a request.

Request flow:

```
Client (OpenAI SDK)
   │  POST /v1/chat/completions
   ▼
Request-ID middleware ──► binds request_id to all logs
   │
   ▼
API layer ──► translates OpenAI request → normalized request
   │
   ▼
Router ──► selects provider by model name
   │         retries (transient) + circuit breaker (sustained outage)
   ▼
Provider (Anthropic / Gemini) ──► adapts to vendor API, translates errors
   │
   ▼
Cost tracking ──► writes tokens/cost/latency to Postgres
   │
   ▼
API layer ──► translates result → OpenAI response
```

## Features

- OpenAI-compatible `/v1/chat/completions` — verified with the official OpenAI SDK
- Multi-provider routing by model name (Anthropic, Gemini)
- Per-provider circuit breaker (CLOSED/OPEN/HALF_OPEN) — fails fast on outage, probes for recovery
- Retries with exponential backoff for transient failures
- Cost tracking to Postgres — every call logged with tokens, USD, latency, provider
- Request-ID tracing threaded through all logs

## A note on cost governance

The cheapest per-token model is not always the cheapest per request. Gemini 2.5
Flash has a lower headline price than Claude Haiku 4.5, but it's a *thinking*
model — for the same prompt it emits a burst of internal reasoning tokens before
the answer, and those tokens are billed as output. In testing, Claude Haiku
returned "Paris" in **4 output tokens**, while Gemini 2.5 Flash spent **~28** on
the identical one-word answer. Across the cost log this compounds to roughly
**9× the output tokens** and — despite the lower unit price — about **8.6× the
cost per request**.

That's a governance insight invisible from a pricing page; it only surfaces when
every call is metered. Because the gateway logs `prompt_tokens`,
`completion_tokens` (thinking included), `provider`, `resolved_model`, and a
computed USD figure for every request, the real per-request economics are
queryable, not guessed. (The Gemini adapter also reserves a dedicated
thinking-token budget so reasoning never starves the answer under a small
`max_tokens` — a correctness fix that fell directly out of this cost work.)

## Benchmarks

Load-tested with [k6](https://k6.io) against the deployed instance (Render free
tier). Reproduce with `GATEWAY_URL=<url> k6 run loadtest/health.js`.

**Health endpoint** — `GET /health`, ramping to 20 concurrent VUs over 60s:

| Metric | Value |
| --- | --- |
| Requests | 1,607 (26.7 req/s) |
| Error rate | 0.00% (0 / 1,607) |
| p50 | 298 ms |
| p90 | 323 ms |
| p95 | 366 ms |
| max | 31.3 s ¹ |

¹ The 31s max (and the inflated 564ms average) is a single free-tier **cold
start** — Render sleeps idle instances and the first request pays the wake-up.
Steady state the endpoint holds **sub-400ms at p95 with zero errors** under 20
concurrent VUs; the ~300ms median is essentially network round-trip to the
free-tier region.

**Completions endpoint** — `POST /v1/chat/completions` (`claude-haiku-4-5`),
ramping to 3 VUs over 35s:

| Metric | Value |
| --- | --- |
| Requests | 87 (2.47 req/s) |
| Error rate | 0.00% (0 / 87) |
| p50 | 915 ms |
| p90 | 1.09 s |
| p95 | 1.21 s |
| min / max | 783 ms / 3.44 s |

End-to-end latency here is **dominated by the upstream model call** — the 783ms
floor is essentially the provider's own response time; the gateway adds routing,
translation, and a Postgres cost write on top. Tested at low concurrency (3 VUs)
since each iteration is a real, paid model request. Zero failures across the run.

## Running locally

Prerequisites: [uv](https://docs.astral.sh/uv/) and Docker (for Postgres).

```bash
# 1. Install dependencies
uv sync

# 2. Configure secrets
cp .env.example .env
#    then set ANTHROPIC_API_KEY and GEMINI_API_KEY in .env
#    (DATABASE_URL is preset to the docker-compose Postgres on host port 5435)

# 3. Start Postgres
docker compose up -d

# 4. Run the gateway — from the project root
uv run uvicorn gateway.main:app --reload --port 8080
```

The app reads three environment variables: `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, and `DATABASE_URL`. Run it from the **project root** so `.env`
and the `gateway` package resolve correctly.

Or run it containerized:

```bash
docker build -t llm-gateway:local .
docker run --rm -p 8080:8080 \
  -e ANTHROPIC_API_KEY="..." -e GEMINI_API_KEY="..." \
  -e DATABASE_URL="postgresql+asyncpg://gateway:gateway@host.docker.internal:5435/gateway" \
  llm-gateway:local
```

## Design decisions

- **A one-method provider protocol (`complete`).** Every provider implements a
  single `complete(CompletionRequest) -> CompletionResult`. The narrow interface
  keeps vendor quirks (Anthropic's top-level `system`, Gemini's thinking budget)
  contained inside each adapter, and adding a provider becomes mechanical.
- **`retryable` is a property of the error, not the router.** Each provider
  catches its vendor's exceptions and tags the resulting `ProviderError` with
  `retryable`. The router just reads that flag — it never needs to know what a 429
  looks like for any given SDK. Error classification lives where the vendor
  knowledge is.
- **Both `requested_model` and `resolved_model` are stored.** The cost log keeps
  the name the client asked for (`claude-haiku-4-5`) and the concrete model that
  served it (`claude-haiku-4-5-20251001`) — the product view and the ops/billing
  view. Collapsing them would lose information.
- **`provider` travels on the result.** Each provider stamps its own name onto the
  `CompletionResult`, so cost logging records the true source with no
  model→provider reverse lookup.

## What I'd add for production

- Semantic + exact caching (built in a sibling project, not ported here)
- Per-API-key rate limiting + auth
- Streaming (SSE) support
- OpenTelemetry distributed tracing
- Per-key cost budgets and alerting
