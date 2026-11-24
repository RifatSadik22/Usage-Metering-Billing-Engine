from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_tenant
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import Tenant
from app.services.meter_service import get_effective_subscription
from app.services.stripe_service import StripeService

router = APIRouter()


@router.post("/billing/checkout")
def checkout(
    tenant: Tenant = Depends(get_authenticated_tenant),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    service = StripeService(settings)
    if not service.configured():
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "STRIPE_NOT_CONFIGURED",
                    "message": "Stripe test mode is not configured.",
                }
            },
        )
    subscription, _ = get_effective_subscription(db, tenant.id)
    if subscription.plan_id == 2:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "ALREADY_PRO",
                    "message": "The tenant is already on the Pro plan.",
                }
            },
        )
    try:
        session = service.create_checkout_session(str(tenant.id), subscription.stripe_customer_id)
        if not subscription.stripe_customer_id:
            subscription.stripe_customer_id = getattr(session, "customer", None)
            db.commit()
        return {"checkout_url": session.url}
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "STRIPE_ERROR",
                    "message": "Could not create Stripe Checkout Session.",
                }
            },
        ) from exc
