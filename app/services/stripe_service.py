import stripe

from app.core.config import Settings


def live_mode_rejected(secret_key: str) -> bool:
    return secret_key.startswith("sk_live_")


class StripeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.stripe_secret_key:
            if live_mode_rejected(settings.stripe_secret_key):
                raise RuntimeError("Live-mode Stripe keys are forbidden")
            stripe.api_key = settings.stripe_secret_key

    def configured(self) -> bool:
        return bool(
            self.settings.stripe_secret_key
            and self.settings.stripe_webhook_secret
            and self.settings.stripe_pro_price_id
        )

    def verify_event(self, raw_body: bytes, signature: str) -> stripe.Event:
        if not signature:
            raise stripe.SignatureVerificationError("Missing Stripe-Signature", signature)
        if not self.settings.stripe_webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")
        event = stripe.Webhook.construct_event(
            raw_body,
            signature,
            self.settings.stripe_webhook_secret,
        )
        if event.get("livemode") is True:
            raise ValueError("Live-mode Stripe events are forbidden")
        return event

    def create_checkout_session(
        self,
        tenant_id: str,
        customer_id: str | None,
    ) -> stripe.checkout.Session:
        if not self.configured():
            raise RuntimeError("Stripe is not configured")
        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": self.settings.stripe_pro_price_id, "quantity": 1}],
            "success_url": self.settings.checkout_success_url,
            "cancel_url": self.settings.checkout_cancel_url,
            "metadata": {"tenant_id": tenant_id},
            "subscription_data": {"metadata": {"tenant_id": tenant_id}},
        }
        if customer_id:
            params["customer"] = customer_id
        return stripe.checkout.Session.create(**params)
