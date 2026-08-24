# LLM Gateway

A multi-LLM gateway that routes generation requests across providers with
retry, circuit breaking, and cost/latency-aware fallback, backed by
Redis-based caching — built to demonstrate real distributed-systems patterns
around a network of unreliable, costed upstream dependencies, not as a thin
wrapper over a single provider's API.

## What this is

A backend service that sits in front of multiple LLM providers and handles
the failure modes and cost tradeoffs of doing that for real:

- **JWT-based auth and per-user multi-tenancy** — access/refresh token pairs
  with refresh rotation (single-use, revoked on every use), and every owned
  resource (projects, prompts, API keys) scoped and returned as `404`, not
  `403`, on cross-user access, so a request can't even confirm another
  user's resource exists.
- **Prompt management** — versioned (append-only, immutable versions),
  taggable, and foldered, with search/filtering across a project's prompts;
  plus a scoped, revocable API-key system (hashed, never stored in
  plaintext) for programmatic access alongside the JWT-based user flow.
- **Multi-provider routing** across two hosted providers (OpenAI, Anthropic)
  and a local model (Ollama), selected dynamically based on recent latency
  and estimated per-token cost — not a static priority list.
- **Retry, circuit breaker, and fallback** — exponential backoff with jitter,
  a per-provider closed/open/half-open circuit breaker, and automatic
  fallback to another provider when one degrades or fails outright.
- **A controllable mock provider** for chaos testing — real hosted providers
  don't fail reliably on command, so a separate, admin-togglable mock server
  (normal / slow / error / timeout / flaky modes) stands in for them when
  testing how the router actually behaves under failure.
- **Redis-backed exact-match caching** for repeated prompt/generation pairs,
  with TTL-only invalidation and hit-rate/latency tracking under a
  realistic (non-uniform) query distribution — fails open on a Redis
  outage rather than breaking generation.


## Stack

- Backend: FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic
- Data: PostgreSQL, Redis
- Providers: OpenAI, Anthropic, local Ollama, plus a controllable mock
  provider server for chaos testing
- Frontend: React + TypeScript + Tailwind CSS (minimal — not the focus of
  this project)

## Getting started

```bash
cp env.example .env
cd backend
python -m venv .venv
.venv\Scripts\activate  # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The mock provider runs as its own process, separate from the main app —
needed so it's independently reachable/killable for chaos testing:

```bash
uvicorn app.mock_provider.server:app --port 9100 --reload
```

Real provider calls need `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` set in `.env`;
Ollama needs `ollama serve` running locally with the target model pulled.
None of these are required to run the gateway against the mock provider.

Caching needs a running Redis (`REDIS_HOST`/`REDIS_PORT` in `.env`,
`CACHE_ENABLED=true` by default). Without one, generation still works as
normal — the cache fails open, so every request just misses instead of
erroring.

## Benchmarks

Chaos-test and load-test results — success rate during a simulated provider
outage, fallback trigger time and recovery time, circuit-breaker threshold
sensitivity across configs, backoff-jitter on vs. off, and cache hit
rate/latency reduction under realistic traffic — are logged with real
numbers, not summarized claims, in [`docs/metrics.md`](docs/metrics.md) as
each benchmark is run.


