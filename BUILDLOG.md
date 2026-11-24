# Build Log

## AI assistance
AI assisted with implementation structure, schema design, test ideas, Docker configuration, and documentation.

## Human/engineering review points
- Idempotency correctness relies on a tenant row lock and database uniqueness, not memory locks.
- Money uses integer micro-USD and an explicit cached-token rounding policy.
- Stripe webhooks require official signature verification and are the only subscription upgrade authority.
- Docker, database, and real Stripe execution remain environment-dependent and must be run locally or in CI.

## Verification and fixes

- Installed Docker Desktop 4.100.1 and started the Docker Engine successfully.
- Started PostgreSQL 16, API, and worker with Docker Compose and verified health.
- Fixed the GitHub Actions failure in `alembic.ini`: missing `qualname` values for configured loggers.
- Fixed migration sequencing by keeping the Stripe event-order column only in migration `002eventorder`.
- Made worker startup depend on healthy API/migrations instead of starting against an unmigrated database.
- Fixed live Stripe key handling to allow only test-mode key prefixes and reject `sk_live_*` and `rk_live_*`.
- Added event timestamp ordering for subscription updates/deletions to prevent older events from restoring stale state.
- Fixed Stripe test-signature generation for the installed SDK and added real PostgreSQL integration coverage.
- Expanded observed suite: 19 passed with 86% application coverage on PostgreSQL.
- Added exact AI-token boundary, HTTP 402, monthly cost rollup, temporary/permanent worker retry tests.
- Real Stripe Checkout and live webhook forwarding are external credential-dependent and remain pending.
