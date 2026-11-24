from sqlalchemy.orm import Session

from app.core.pricing import PRICING_VERSION, format_usd
from app.models.models import Plan, Subscription, Tenant
from app.services.meter_service import aggregate_usage, usage_period


def get_usage(db: Session, tenant: Tenant, subscription: Subscription, plan: Plan) -> dict:
    period = usage_period()
    usage = aggregate_usage(db, tenant.id, period)
    return {
        "tenant_id": str(tenant.id),
        "current_plan": plan.slug,
        "subscription_status": subscription.status,
        "usage_period": period.isoformat(),
        "used_api_calls": usage["api_calls"],
        "api_call_limit": plan.monthly_api_call_limit,
        "remaining_api_calls": max(0, plan.monthly_api_call_limit - usage["api_calls"]),
        "used_ai_tokens": usage["total_tokens"],
        "ai_token_limit": plan.monthly_ai_token_limit,
        "remaining_ai_tokens": max(0, plan.monthly_ai_token_limit - usage["total_tokens"]),
        "fresh_input_tokens": usage["fresh_input_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"],
        "metered_cost_micro_usd": usage["cost_micro_usd"],
        "metered_cost_usd": format_usd(usage["cost_micro_usd"]),
        "pricing_version": PRICING_VERSION,
        "subscription_fee_usd": "19.00" if plan.slug == "pro" else "0.00",
    }
