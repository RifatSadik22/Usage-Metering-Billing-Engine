# Evidence

## Observed verification — 2026-11-25

### GitHub Actions

- Implementation commit `004f6bf` passed workflow `45502550873`; final evidence commit `ee951a9` passed workflow `45502751819`. Both runs completed successfully on `master`.
- CI observed `19 passed, 1 warning in 5.48s`, coverage `94%`, and Ruff `All checks passed`.

### Local environment

- Docker Desktop 4.100.1 / Docker Engine 29.9.3: installed and running.
- Docker Compose: PostgreSQL 16, API, and worker all started.
- PostgreSQL: healthy on `localhost:5432`.
- Migration state: `002eventorder (head)`.
- API health: `HTTP 200 {"status":"healthy","database":"healthy"}`.
- Seeded usage: `HTTP 200`, tenant A, Free plan, 1,000 API limit, 100,000 token limit.

### Automated verification

Observed from the final clean, dedicated PostgreSQL test database run on 2026-11-25:

```text
19 passed, 1 warning in 3.53s (local Docker test runner)
TOTAL coverage: 94%
Ruff: All checks passed
```

The one warning is a Starlette deprecation notice about its `httpx`-based TestClient; no test failed.

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
- Missing and forged signature handling (HTTP 400, unchanged subscription state)
- Duplicate webhook handling
- Mocked Checkout creation with the configured server-side recurring price
- Tenant-bound Checkout metadata and Checkout URL response
- Signed mocked Free-to-Pro lifecycle and updated Pro limits
- Signed subscription update, cancellation/downgrade, and stale-event rejection
- Forged signature rejection with unchanged subscription state
- Live-key rejection
- Worker result processing
- Worker temporary failure retry scheduling
- Worker permanent failure and structured exhaustion alert
- Worker tests isolate durable job rows; test workflow uses a fresh dedicated PostgreSQL database

### Commands observed

```powershell
docker compose up --build -d
docker compose exec -T api sh -c "pip install -e '.[test]' && python -m scripts.test"
ruff check .
```

The documented test command was executed in the API container. `scripts.test` created the dedicated test database, applied both migrations, seeded demo tenants/plans, and executed the full suite without using Stripe credentials.

## Worked pricing example

For 1 API call, 1,000 fresh input, 500 cached input, 200 output, and 100 reasoning tokens:

- API: 1,000 micro-USD
- Fresh: 1,000 micro-USD
- Cached: 125 micro-USD
- Output: 800 micro-USD
- Reasoning: 400 micro-USD
- Total: **3,325 micro-USD ($0.003325)**

## Stripe verification scope

Stripe SDK Checkout is verified with deterministic mocked SDK responses. Webhook fixtures are signed using a local test-only HMAC secret and pass through the real Stripe SDK's signature verifier. These fixtures verify backend behavior but do not represent a Stripe-hosted Checkout, an external Stripe API call, or a real payment. The project claims no real Checkout occurred.

## Official acceptance probes

1. **Idempotent metering:** `test_generate_success_and_identical_retry` and `test_concurrent_duplicate_is_exactly_once` passed; replayed identical requests retained one event and one logical response.
2. **Quota boundary:** `test_api_quota_boundary_and_next_request` passed; the 1,000th Free API call succeeded and the next returned 429 with `Retry-After`. `test_ai_token_quota_boundary` passed; 99,900 + 100 tokens succeeded and the next token returned 429.
3. **Subscription upgrade and usage:** `test_mocked_checkout_and_signed_free_pro_lifecycle` passed. The mocked SDK received subscription mode, authenticated tenant metadata, and the server-configured recurring price; the Checkout URL was returned. After a cryptographically signed `checkout.session.completed` fixture, `GET /usage` returned Pro limits of 10,000 API calls and 1,000,000 tokens. This is explicitly mocked SDK/fixture verification, not Stripe-hosted Checkout.
4. **Webhook authenticity and replay:** `test_missing_and_forged_signatures_are_rejected_without_state_change` passed with HTTP 400 and unchanged plan. The lifecycle test verified one-time signed-event processing, replay dedupe, subscription update, cancellation to Free, and rejection of an older update.
5. **Pricing:** `test_worked_example` passed with exactly 3,325 micro-USD ($0.003325), including 125 micro-USD for 500 cached input tokens; `test_monthly_persisted_cost_rollup` verified three persisted events aggregate to 9,975 micro-USD.

## Shared backend requirements

| Requirement | Evidence |
|---|---|
| Layered architecture | HTTP routes, schemas, services, models, and worker are separated under `app/` and `scripts/`. |
| Boundary validation | Pydantic rejects invalid/negative token quantities; API-key and idempotency header tests cover invalid requests. |
| Background processing with retries and failure alerts | PostgreSQL job tests verify successful summary processing, retry scheduling, permanent failure, and structured alert logging. |
| Real persistence and migrations | Fresh PostgreSQL Compose startup and Alembic upgrade to `002eventorder` completed; tenant/period index and constraints are migration-backed. |
| Idempotency | PostgreSQL tests verify identical retries and concurrent duplicate requests create one usage event. |
| Secrets hygiene | Stripe values are environment-only; tracked-file scan and clean Git status are verified before submission commit. |
| Cost tracking and budget guard | Integer micro-USD per event, persisted monthly rollups, exact pricing test, and API/token quota boundary tests are covered. |

## Required submission pack

| File | Status |
|---|---|
| `README.md` | Present; run, seed, test, API, limitations, and regional Stripe testing strategy documented. |
| `capstone.yaml` | Present and parsed; Docker run, seed, and isolated test commands are defined and exercised. |
| `EVIDENCE.md` | Present; observed outputs and all five acceptance probes are recorded. |
| `BUILDLOG.md` | Present; AI assistance, implementation decisions, and regional testing scope are stated honestly. |
| `.env.example` | Present with placeholders only; actual `.env` is ignored and not tracked. |
