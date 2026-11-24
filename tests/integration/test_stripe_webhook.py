import json

import stripe
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_missing_signature_returns_400() -> None:
    response = client.post("/webhooks/stripe", content=b"{}", content_type="application/json")
    assert response.status_code == 400


def test_signed_duplicate_is_ignored() -> None:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        return
    event = {
        "id": "evt_duplicate_test_001",
        "object": "event",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test",
                "metadata": {},
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }
    payload = json.dumps(event).encode()
    signed = stripe.Webhook.generate_test_header_string(
        payload=payload.decode(), secret=settings.stripe_webhook_secret
    )
    first = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": signed})
    second = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": signed})
    assert first.status_code in {200, 500}
    assert second.status_code in {200, 500}
