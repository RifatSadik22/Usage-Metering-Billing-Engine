import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import billing, webhooks
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.security import hash_api_key
from app.main import app
from app.models.models import Plan, ProcessedStripeEvent, Subscription, Tenant

client = TestClient(app)
TEST_WEBHOOK_SECRET = "whsec_local_fixture_only"
TEST_STRIPE_SETTINGS = Settings(
    stripe_secret_key="sk_test_local_fixture_only",
    stripe_webhook_secret=TEST_WEBHOOK_SECRET,
    stripe_pro_price_id="price_local_pro_monthly",
    checkout_success_url="http://localhost:8000/docs?checkout=success",
    checkout_cancel_url="http://localhost:8000/docs?checkout=cancel",
)


def signed_event(event_type: str, data: dict, created: int, event_id: str | None = None):
    event = {
        "id": event_id or f"evt_fixture_{uuid4().hex}",
        "object": "event",
        "type": event_type,
        "created": created,
        "livemode": False,
        "data": {"object": data},
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    digest = hmac.new(
        TEST_WEBHOOK_SECRET.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return payload, f"t={timestamp},v1={digest}", event["id"]


def post_signed_event(event_type: str, data: dict, created: int, event_id: str | None = None):
    payload, signature, resolved_event_id = signed_event(event_type, data, created, event_id)
    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": signature},
    )
    return response, resolved_event_id


def tenant_a():
    with SessionLocal() as db:
        return db.scalar(
            select(Tenant).where(
                Tenant.api_key_hash == hash_api_key(get_settings().demo_tenant_a_api_key)
            )
        )


def reset_tenant_to_free(tenant_id) -> None:
    with SessionLocal.begin() as db:
        free = db.scalar(select(Plan).where(Plan.slug == "free"))
        sub = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant_id))
        sub.plan_id = free.id
        sub.status = "free"
        sub.stripe_customer_id = None
        sub.stripe_subscription_id = None
        sub.last_stripe_event_created = None


def test_missing_and_forged_signatures_are_rejected_without_state_change(monkeypatch):
    monkeypatch.setattr(webhooks, "get_settings", lambda: TEST_STRIPE_SETTINGS)
    tenant = tenant_a()
    before = client.get(
        "/usage",
        headers={"X-API-Key": get_settings().demo_tenant_a_api_key},
    ).json()
    unsigned = client.post("/webhooks/stripe", content=b"{}")
    forged = client.post(
        "/webhooks/stripe",
        content=b'{"id":"evt_forged","type":"customer.subscription.deleted"}',
        headers={"Stripe-Signature": "t=1,v1=forged"},
    )
    after = client.get(
        "/usage",
        headers={"X-API-Key": get_settings().demo_tenant_a_api_key},
    ).json()
    assert unsigned.status_code == 400
    assert forged.status_code == 400
    assert before["tenant_id"] == str(tenant.id)
    assert after["current_plan"] == before["current_plan"]


def test_mocked_checkout_and_signed_free_pro_lifecycle(monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: TEST_STRIPE_SETTINGS)
    monkeypatch.setattr(webhooks, "get_settings", lambda: TEST_STRIPE_SETTINGS)
    tenant = tenant_a()
    reset_tenant_to_free(tenant.id)
    calls = []

    def create_session(**params):
        calls.append(params)
        return SimpleNamespace(
            id="cs_test_fixture",
            url="https://checkout.stripe.test/session_fixture",
            customer="cus_fixture_a",
        )

    monkeypatch.setattr(
        "app.services.stripe_service.stripe.checkout.Session.create",
        create_session,
    )
    headers = {"X-API-Key": get_settings().demo_tenant_a_api_key}
    before = client.get("/usage", headers=headers)
    assert before.status_code == 200
    assert before.json()["current_plan"] == "free"

    checkout = client.post("/billing/checkout", headers=headers)
    assert checkout.status_code == 200
    assert checkout.json() == {"checkout_url": "https://checkout.stripe.test/session_fixture"}
    assert calls == [
        {
            "mode": "subscription",
            "line_items": [{"price": "price_local_pro_monthly", "quantity": 1}],
            "success_url": "http://localhost:8000/docs?checkout=success",
            "cancel_url": "http://localhost:8000/docs?checkout=cancel",
            "metadata": {"tenant_id": str(tenant.id)},
            "subscription_data": {"metadata": {"tenant_id": str(tenant.id)}},
        }
    ]

    completed, event_id = post_signed_event(
        "checkout.session.completed",
        {
            "id": "cs_test_fixture",
            "metadata": {"tenant_id": str(tenant.id)},
            "customer": "cus_fixture_a",
            "subscription": "sub_fixture_a",
        },
        created=2_000,
    )
    assert completed.status_code == 200
    assert completed.json() == {"received": True, "duplicate": False}
    after_upgrade = client.get("/usage", headers=headers)
    assert after_upgrade.status_code == 200
    assert after_upgrade.json()["current_plan"] == "pro"
    assert after_upgrade.json()["api_call_limit"] == 10_000
    assert after_upgrade.json()["ai_token_limit"] == 1_000_000
    assert after_upgrade.json()["subscription_status"] == "active"

    with SessionLocal() as db:
        stored = db.scalar(
            select(ProcessedStripeEvent).where(ProcessedStripeEvent.stripe_event_id == event_id)
        )
        assert stored is not None
        assert stored.event_type == "checkout.session.completed"

    replay_payload, replay_signature, _ = signed_event(
        "checkout.session.completed",
        {
            "id": "cs_test_fixture",
            "metadata": {"tenant_id": str(tenant.id)},
            "customer": "cus_fixture_a",
            "subscription": "sub_fixture_a",
        },
        created=2_000,
        event_id=event_id,
    )
    replay = client.post(
        "/webhooks/stripe",
        content=replay_payload,
        headers={"Stripe-Signature": replay_signature},
    )
    assert replay.status_code == 200
    assert replay.json() == {"received": True, "duplicate": True}

    update, _ = post_signed_event(
        "customer.subscription.updated",
        {
            "id": "sub_fixture_a",
            "status": "active",
            "metadata": {"tenant_id": str(tenant.id)},
        },
        created=2_100,
    )
    assert update.status_code == 200
    assert client.get("/usage", headers=headers).json()["current_plan"] == "pro"

    deleted, _ = post_signed_event(
        "customer.subscription.deleted",
        {"id": "sub_fixture_a", "metadata": {"tenant_id": str(tenant.id)}},
        created=2_200,
    )
    assert deleted.status_code == 200
    downgraded = client.get("/usage", headers=headers).json()
    assert downgraded["current_plan"] == "free"
    assert downgraded["subscription_status"] == "canceled"

    stale_update, _ = post_signed_event(
        "customer.subscription.updated",
        {
            "id": "sub_fixture_a",
            "status": "active",
            "metadata": {"tenant_id": str(tenant.id)},
        },
        created=2_150,
    )
    assert stale_update.status_code == 200
    still_free = client.get("/usage", headers=headers).json()
    assert still_free["current_plan"] == "free"
    assert still_free["subscription_status"] == "canceled"

    reset_tenant_to_free(tenant.id)
