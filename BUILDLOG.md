# Build Log

## AI assistance
AI assisted with implementation structure, schema design, test ideas, Docker configuration, and documentation.

## Human/engineering review points
- Idempotency correctness relies on a tenant row lock and database uniqueness, not memory locks.
- Money uses integer micro-USD and an explicit cached-token rounding policy.
- Stripe webhooks require official signature verification and are the only subscription upgrade authority.
- Docker and PostgreSQL are locally verified; real Stripe-hosted Checkout is not part of this regionally restricted fixture-verification path.

## Verification and fixes

- Installed Docker Desktop 4.100.1 and started the Docker Engine successfully.
- Started PostgreSQL 16, API, and worker with Docker Compose and verified health.
- Fixed the GitHub Actions failure in `alembic.ini`: missing `qualname` values for configured loggers.
- Fixed migration sequencing by keeping the Stripe event-order column only in migration `002eventorder`.
- Made worker startup depend on healthy API/migrations instead of starting against an unmigrated database.
- Fixed live Stripe key handling to allow only test-mode key prefixes and reject `sk_live_*` and `rk_live_*`.
- Added event timestamp ordering for subscription updates/deletions to prevent older events from restoring stale state.
- Fixed Stripe test-signature generation for the installed SDK and added real PostgreSQL integration coverage.
- Final observed suite: 19 passed with 94% application coverage on an isolated PostgreSQL test database.
- Added exact AI-token boundary, HTTP 402, monthly cost rollup, temporary/permanent worker retry tests.
- Bangladesh is unavailable during Stripe registration. FlyRank's general response to another intern facing the same regional restriction permits SDK-based mocked/test fixtures as an alternative.
- Preserved the official Stripe SDK integration and test-mode Checkout implementation. Added deterministic mocked Checkout SDK tests and signed webhook fixture tests; these validate application behavior but do not claim a Stripe-hosted Checkout occurred.
- Mock fixtures use a local signing secret only in tests. Production request handling still verifies Stripe signatures and does not manufacture payment success.
- Real Stripe account creation and hosted test Checkout are not required for this regionally restricted submission under the cited alternative.
- Added `scripts.test`, which recreates only the named disposable `billing_capstone_test` database, then migrates, seeds, and runs coverage tests. The evaluator command requires no Stripe credentials and does not clear the app's normal database.
- Evaluator test instructions use `capstone.yaml`'s Docker-based run, seed, and test commands; test fixtures require no external Stripe credentials.
