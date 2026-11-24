from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

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
