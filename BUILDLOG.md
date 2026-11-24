# Build Log

## AI assistance
AI assisted with implementation structure, schema design, test ideas, Docker configuration, and documentation.

## Human/engineering review points
- Idempotency correctness relies on a tenant row lock and database uniqueness, not memory locks.
- Money uses integer micro-USD and an explicit cached-token rounding policy.
- Stripe webhooks require official signature verification and are the only subscription upgrade authority.
- Docker, database, and real Stripe execution remain environment-dependent and must be run locally or in CI.
