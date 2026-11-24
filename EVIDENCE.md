# Evidence

## Observed verification — 2026-11-24

### GitHub Actions

- Failed run `45493317635` identified root cause: `alembic.ini` logging configuration lacked `qualname`.
- Remediation commit: `85c2c9d`.
- Verified rerun `45497699843`: **success** on `master`.

### Local environment

- Docker Desktop 4.100.1 / Docker Engine 29.9.3: installed and running.
- Docker Compose: PostgreSQL 16, API, and worker all started.
- PostgreSQL: healthy on `localhost:5432`.
- Migration state: `002eventorder (head)`.
- API health: `HTTP 200 {"status":"healthy","database":"healthy"}`.
- Seeded usage: `HTTP 200`, tenant A, Free plan, 1,000 API limit, 100,000 token limit.

### Automated verification

Observed from the final clean-PostgreSQL run on 2026-11-25:

```text
19 passed in 2.91s
TOTAL coverage: 86%
Ruff: All checks passed
```

Covered real PostgreSQL integration scenarios include:

- Health and seeded usage
- Successful generation and identical retry
- Different-payload idempotency conflict
- Missing API key and invalid API key
- Negative quantity validation
- Tenant isolation
- Concurrent duplicate metering with exactly one usage event
- Exact API quota boundary plus first request beyond 429
- Exact AI-token quota boundary: 99,900 + 100 succeeds and the next token is rejected
- HTTP 402 past-due subscription behavior
- Monthly persisted cost rollup of 3 × 3,325 micro-USD = 9,975 micro-USD
- `Retry-After` header
- Missing and valid signed webhook handling
- Duplicate webhook handling
- Live-key rejection
- Worker result processing
- Worker temporary failure retry scheduling
- Worker permanent failure and structured exhaustion alert

### Commands observed

```powershell
docker compose up --build -d
docker compose down -v
docker compose up --build -d
alembic upgrade head
pytest -q --cov=app --cov-report=term-missing
ruff check .
```

## Worked pricing example

For 1 API call, 1,000 fresh input, 500 cached input, 200 output, and 100 reasoning tokens:

- API: 1,000 micro-USD
- Fresh: 1,000 micro-USD
- Cached: 125 micro-USD
- Output: 800 micro-USD
- Reasoning: 400 micro-USD
- Total: **3,325 micro-USD ($0.003325)**

## Environment status
- Python dependencies: installed.
- Docker and PostgreSQL: Docker Desktop and a PostgreSQL 16 Compose service are available locally and verified.
- Real Stripe Checkout: pending because no test-mode credentials were provided.

## Official acceptance probes

1. **Identical billable retries:** verified in `test_generate_success_and_identical_retry` and `test_concurrent_duplicate_is_exactly_once`; second/concurrent logical retries remain one usage event.
2. **Exact quota boundary:** verified in `test_api_quota_boundary_and_next_request`; 1,000th request succeeds and the next returns 429 with `Retry-After`.
3. **Stripe Free-to-Pro Checkout:** **PENDING**. A real test Checkout cannot be claimed without `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `STRIPE_PRO_PRICE_ID`. The local webhook and signed-event paths are implemented and tested with synthetic secrets.
4. **Forged and replayed webhooks:** missing signatures return 400; locally signed test events are processed; duplicate event IDs are ignored. **Real Stripe replay pending** external credentials/CLI forwarding.
5. **Pinned pricing:** `test_worked_example` observed exactly 3,325 micro-USD ($0.003325), including 125 micro-USD for 500 cached input tokens.
