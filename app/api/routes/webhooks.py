import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import Plan, ProcessedStripeEvent, Subscription
from app.services.stripe_service import StripeService

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    service = StripeService(get_settings())
    try:
        event = service.verify_event(raw, stripe_signature or "")
    except (stripe.SignatureVerificationError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_STRIPE_SIGNATURE",
                    "message": "Invalid or missing Stripe webhook signature.",
                }
            },
        ) from exc

    event_id = event["id"]
    event_type = event["type"]
    event_created = int(event.get("created", 0))
    existing = db.scalar(
        select(ProcessedStripeEvent).where(ProcessedStripeEvent.stripe_event_id == event_id)
    )
    if existing:
        return {"received": True, "duplicate": True}

    data = event["data"]["object"]
    try:
        if event_type == "checkout.session.completed":
            tenant_id = data.get("metadata", {}).get("tenant_id")
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")
            if not tenant_id:
                raise ValueError("Missing tenant metadata")
            sub = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant_id))
            if sub is None:
                sub = Subscription(tenant_id=tenant_id, status="inactive")
            stale = (
                event_created
                and sub.last_stripe_event_created
                and event_created < sub.last_stripe_event_created
            )
            if not stale:
                pro = db.scalar(select(Plan).where(Plan.slug == "pro"))
                sub.plan_id = pro.id
                sub.status = "active"
                sub.stripe_customer_id = str(customer_id) if customer_id else sub.stripe_customer_id
                sub.stripe_subscription_id = (
                    str(subscription_id) if subscription_id else sub.stripe_subscription_id
                )
                sub.last_stripe_event_created = event_created or sub.last_stripe_event_created

        elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
            subscription_id = data.get("id")
            sub = db.scalar(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == str(subscription_id)
                )
            )
            if sub is None:
                metadata = data.get("metadata", {})
                tenant_id = metadata.get("tenant_id")
                if tenant_id:
                    sub = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant_id))
            if sub is not None:
                pro = db.scalar(select(Plan).where(Plan.slug == "pro"))
                free = db.scalar(select(Plan).where(Plan.slug == "free"))
                stale = (
                    event_created
                    and sub.last_stripe_event_created
                    and event_created < sub.last_stripe_event_created
                )
                if not stale:
                    if event_type == "customer.subscription.deleted":
                        sub.status = "canceled"
                        sub.plan_id = free.id
                    else:
                        status = data.get("status", "incomplete")
                        sub.status = status
                        sub.plan_id = pro.id if status in {"active", "trialing"} else free.id
                        sub.stripe_subscription_id = (
                            str(subscription_id) if subscription_id else sub.stripe_subscription_id
                        )
                        sub.billing_period_start = None
                        sub.billing_period_end = None
                    sub.last_stripe_event_created = event_created or sub.last_stripe_event_created

        db.add(
            ProcessedStripeEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                processing_metadata={"livemode": event.get("livemode", False)},
            )
        )
        db.commit()
        return {"received": True, "duplicate": False}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "WEBHOOK_PROCESSING_FAILED",
                    "message": "Webhook processing failed; Stripe should retry.",
                }
            },
        ) from exc
