| Requirement | Implementation | Verification |
|---|---|---|
| Idempotent metering | Tenant lock + idempotency record + usage-event unique constraint | Integration tests |
| Quotas | PostgreSQL transaction and plan limits | Boundary/concurrency tests |
| Money | Integer micro-USD pricing module | Unit tests + EVIDENCE |
| Stripe | Official SDK + signature verification + dedupe table | Mocked signed-webhook tests |
| Persistence | Alembic PostgreSQL schema and migrations | Migration startup |
| Background worker | Durable PostgreSQL jobs and bounded retries | Worker unit/integration tests |
| Tenant isolation | SHA-256 API-key lookup and tenant-scoped queries | Isolation tests |
