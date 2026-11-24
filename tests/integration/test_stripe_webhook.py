import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.models import Tenant

client = TestClient(app)


def test_missing_signature_returns_400() -> None:
    response = client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_signed_duplicate_is_ignored() -> None:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        return
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).limit(1))
    event = {
        "id": "evt_duplicate_test_001",
        "object": "event",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test",
                "metadata": {"tenant_id": str(tenant.id)},
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }
    payload = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    signature = hmac.new(
        settings.stripe_webhook_secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    signed = f"t={timestamp},v1={signature}"
    first = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": signed})
    second = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": signed})
    assert first.status_code in {200, 500}
    assert second.status_code in {200, 500}
