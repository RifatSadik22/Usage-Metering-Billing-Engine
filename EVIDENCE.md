# Evidence

## Worked pricing example

For 1 API call, 1,000 fresh input, 500 cached input, 200 output, and 100 reasoning tokens:

- API: 1,000 micro-USD
- Fresh: 1,000 micro-USD
- Cached: 125 micro-USD
- Output: 800 micro-USD
- Reasoning: 400 micro-USD
- Total: **3,325 micro-USD ($0.003325)**

The automated test must observe this exact result.

## Verification commands

Record observed local output for:

```text
pytest
ruff check .
docker compose up --build -d
curl http://localhost:8000/health
```

Post-execution outputs should be appended here; do not claim execution that was not run.

## Environment status

- Python dependencies: installed and unit tests passed locally.
- PostgreSQL integration: pending in this Windows environment because Docker is unavailable and no PostgreSQL server executable was found.
- Real Stripe Checkout: pending because no test-mode credentials were provided.
