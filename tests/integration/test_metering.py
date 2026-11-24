from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_api_key
from app.main import app
from app.models.models import Tenant, UsageEvent

client = TestClient(app)


def headers(key: str, idem: str) -> dict:
    return {"X-API-Key": key, "Idempotency-Key": idem}


def test_health_and_seeded_usage(seeded_database) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    response = client.get("/usage", headers={"X-API-Key": get_settings().demo_tenant_a_api_key})
    assert response.status_code == 200
    assert response.json()["api_call_limit"] == 1000


def test_generate_success_and_identical_retry(seeded_database) -> None:
    key = "request-integration-001"
    payload = {
        "input_tokens": 1000,
        "cached_input_tokens": 500,
        "output_tokens": 200,
        "reasoning_tokens": 100,
    }
    first = client.post(
        "/generate", headers=headers(get_settings().demo_tenant_a_api_key, key), json=payload
    )
    assert first.status_code == 200
    body = first.json()
    assert body["cost"]["micro_usd"] == 3325
    second = client.post(
        "/generate", headers=headers(get_settings().demo_tenant_a_api_key, key), json=payload
    )
    assert second.status_code == 200
    assert second.json() == body


def test_different_payload_conflicts(seeded_database) -> None:
    payload = {
        "input_tokens": 1,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    key = "request-conflict-001"
    assert (
        client.post(
            "/generate", headers=headers(get_settings().demo_tenant_a_api_key, key), json=payload
        ).status_code
        == 200
    )
    changed = dict(payload, output_tokens=1)
    response = client.post(
        "/generate", headers=headers(get_settings().demo_tenant_a_api_key, key), json=changed
    )
    assert response.status_code == 409


def test_auth_and_validation(seeded_database) -> None:
    assert client.get("/usage").status_code == 401
    assert client.get("/usage", headers={"X-API-Key": "invalid_api_key"}).status_code == 401
    payload = {
        "input_tokens": -1,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    response = client.post(
        "/generate",
        headers=headers(get_settings().demo_tenant_a_api_key, "bad-input-001"),
        json=payload,
    )
    assert response.status_code == 422


def test_tenant_isolation(seeded_database) -> None:
    tenant_a = client.get("/usage", headers={"X-API-Key": get_settings().demo_tenant_a_api_key})
    tenant_b = client.get("/usage", headers={"X-API-Key": get_settings().demo_tenant_b_api_key})
    assert tenant_a.status_code == 200
    assert tenant_b.status_code == 200
    assert tenant_a.json()["tenant_id"] != tenant_b.json()["tenant_id"]


def test_concurrent_duplicate_is_exactly_once(seeded_database) -> None:
    payload = {
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    headers_for_request = {
        "X-API-Key": get_settings().demo_tenant_b_api_key,
        "Idempotency-Key": "concurrent-duplicate-001",
    }

    def send() -> int:
        return client.post("/generate", headers=headers_for_request, json=payload).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: send(), range(8)))
    assert set(statuses) == {200}

    with SessionLocal() as db:
        tenant = db.scalar(
            select(Tenant).where(
                Tenant.api_key_hash == hash_api_key(get_settings().demo_tenant_b_api_key)
            )
        )
        count = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant.id,
                UsageEvent.idempotency_key == "concurrent-duplicate-001",
            )
            .count()
        )
    assert count == 1


def test_api_quota_boundary_and_next_request(seeded_database) -> None:
    with SessionLocal.begin() as db:
        tenant = db.scalar(
            select(Tenant).where(
                Tenant.api_key_hash == hash_api_key(get_settings().demo_tenant_b_api_key)
            )
        )
        existing = db.query(UsageEvent).filter(UsageEvent.tenant_id == tenant.id).count()
        for index in range(max(0, 999 - existing)):
            db.add(
                UsageEvent(
                    tenant_id=tenant.id,
                    idempotency_key=f"seed-quota-{index}",
                    request_fingerprint="test",
                    usage_type="generate",
                    api_call_quantity=1,
                    fresh_input_tokens=0,
                    cached_input_tokens=0,
                    output_tokens=0,
                    reasoning_tokens=0,
                    total_quota_counted_tokens=0,
                    cost_micro_usd=1000,
                    pricing_version="demo-2026-01",
                    usage_period=__import__("datetime")
                    .datetime.now(__import__("datetime").UTC)
                    .date()
                    .replace(day=1),
                )
            )

    boundary = client.post(
        "/generate",
        headers=headers(get_settings().demo_tenant_b_api_key, "quota-exact-boundary"),
        json={
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
        },
    )
    assert boundary.status_code == 200

    exhausted = client.post(
        "/generate",
        headers=headers(get_settings().demo_tenant_b_api_key, "quota-one-past"),
        json={
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
        },
    )
    assert exhausted.status_code == 429
    assert exhausted.headers["Retry-After"].isdigit()
