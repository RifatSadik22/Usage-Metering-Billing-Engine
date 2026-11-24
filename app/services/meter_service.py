import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pricing import PRICING_VERSION, calculate_cost, format_usd
from app.models.models import IdempotencyRecord, Plan, Subscription, Tenant, UsageEvent


def usage_period(dt: datetime | None = None) -> object:
    dt = dt or datetime.now(UTC)
    return dt.date().replace(day=1)


def fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def month_reset_at(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=UTC)
    return datetime(now.year, now.month + 1, 1, tzinfo=UTC)


def retry_after_seconds(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    reset = month_reset_at(now)
    return max(1, int((reset - now).total_seconds()))


def get_effective_subscription(db: Session, tenant_id) -> tuple[Subscription, Plan]:
    subscription = db.scalar(
        select(Subscription).where(Subscription.tenant_id == tenant_id).with_for_update()
    )
    if subscription is None:
        plan = db.scalar(select(Plan).where(Plan.slug == "free"))
        if plan is None:
            raise RuntimeError("Free plan is not seeded")
        return Subscription(tenant_id=tenant_id, plan_id=plan.id, status="inactive"), plan
    plan = db.get(Plan, subscription.plan_id)
    if plan is None:
        raise RuntimeError("Subscription plan is missing")
    return subscription, plan


def aggregate_usage(db: Session, tenant_id, period) -> dict:
    result = db.execute(
        select(
            func.coalesce(func.sum(UsageEvent.api_call_quantity), 0),
            func.coalesce(func.sum(UsageEvent.fresh_input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.cached_input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
            func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0),
            func.coalesce(func.sum(UsageEvent.total_quota_counted_tokens), 0),
            func.coalesce(func.sum(UsageEvent.cost_micro_usd), 0),
        ).where(UsageEvent.tenant_id == tenant_id, UsageEvent.usage_period == period)
    ).one()
    return {
        "api_calls": int(result[0]),
        "fresh_input_tokens": int(result[1]),
        "cached_input_tokens": int(result[2]),
        "output_tokens": int(result[3]),
        "reasoning_tokens": int(result[4]),
        "total_tokens": int(result[5]),
        "cost_micro_usd": int(result[6]),
    }


class MeterService:
    def generate(
        self,
        db: Session,
        tenant: Tenant,
        idempotency_key: str,
        payload: dict,
    ) -> tuple[int, dict]:
        fp = fingerprint(payload)

        db.execute(select(Tenant.id).where(Tenant.id == tenant.id).with_for_update()).scalar_one()
        existing = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant.id,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if existing:
            if existing.request_fingerprint != fp:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "IDEMPOTENCY_KEY_REUSE",
                            "message": "This idempotency key was used with a different request.",
                        }
                    },
                )
            return existing.original_status, existing.original_body

        subscription, plan = get_effective_subscription(db, tenant.id)
        payment_statuses = {"active", "trialing"}
        if subscription.status not in payment_statuses and subscription.status not in {
            "inactive",
            "free",
        }:
            status = 402
            body = {
                "error": {
                    "code": "PAYMENT_REQUIRED",
                    "message": "An active paid subscription is required.",
                    "subscription_status": subscription.status,
                }
            }
            db.add(
                IdempotencyRecord(
                    tenant_id=tenant.id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fp,
                    original_status=status,
                    original_body=body,
                )
            )
            db.commit()
            return status, body

        period = usage_period()
        usage = aggregate_usage(db, tenant.id, period)
        fresh = payload["input_tokens"]
        cached = payload["cached_input_tokens"]
        output = payload["output_tokens"]
        reasoning = payload["reasoning_tokens"]
        requested_tokens = fresh + cached + output + reasoning

        if usage["api_calls"] + 1 > plan.monthly_api_call_limit:
            status = 429
            body = {
                "error": {
                    "code": "QUOTA_EXCEEDED",
                    "message": "Monthly API call quota exceeded.",
                    "resource": "api_calls",
                    "used": usage["api_calls"],
                    "limit": plan.monthly_api_call_limit,
                    "requested": 1,
                }
            }
            db.add(
                IdempotencyRecord(
                    tenant_id=tenant.id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fp,
                    original_status=status,
                    original_body=body,
                )
            )
            db.commit()
            raise QuotaExceeded(status, body)
        if usage["total_tokens"] + requested_tokens > plan.monthly_ai_token_limit:
            status = 429
            body = {
                "error": {
                    "code": "QUOTA_EXCEEDED",
                    "message": "Monthly AI token quota exceeded.",
                    "resource": "ai_tokens",
                    "used": usage["total_tokens"],
                    "limit": plan.monthly_ai_token_limit,
                    "requested": requested_tokens,
                }
            }
            db.add(
                IdempotencyRecord(
                    tenant_id=tenant.id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fp,
                    original_status=status,
                    original_body=body,
                )
            )
            db.commit()
            raise QuotaExceeded(status, body)

        cost = calculate_cost(fresh, cached, output, reasoning)
        event = UsageEvent(
            tenant_id=tenant.id,
            idempotency_key=idempotency_key,
            request_fingerprint=fp,
            usage_type="generate",
            api_call_quantity=1,
            fresh_input_tokens=fresh,
            cached_input_tokens=cached,
            output_tokens=output,
            reasoning_tokens=reasoning,
            total_quota_counted_tokens=requested_tokens,
            cost_micro_usd=cost.total_micro_usd,
            pricing_version=PRICING_VERSION,
            usage_period=period,
        )
        db.add(event)
        db.flush()

        remaining_usage = aggregate_usage(db, tenant.id, period)
        body = {
            "usage_event_id": str(event.id),
            "result": "Generation completed successfully (simulated).",
            "recorded_usage": {
                "api_calls": 1,
                "fresh_input_tokens": fresh,
                "cached_input_tokens": cached,
                "output_tokens": output,
                "reasoning_tokens": reasoning,
                "total_quota_counted_tokens": requested_tokens,
            },
            "cost": {
                "micro_usd": cost.total_micro_usd,
                "formatted_usd": format_usd(cost.total_micro_usd),
                "pricing_version": PRICING_VERSION,
            },
            "remaining_quota": {
                "api_calls": plan.monthly_api_call_limit - remaining_usage["api_calls"],
                "ai_tokens": plan.monthly_ai_token_limit - remaining_usage["total_tokens"],
            },
            "pricing": {
                "api_call_micro_usd": cost.api_call_micro_usd,
                "fresh_input_micro_usd": cost.fresh_input_micro_usd,
                "cached_input_micro_usd": cost.cached_input_micro_usd,
                "output_micro_usd": cost.output_micro_usd,
                "reasoning_micro_usd": cost.reasoning_micro_usd,
            },
        }
        db.add(
            IdempotencyRecord(
                tenant_id=tenant.id,
                idempotency_key=idempotency_key,
                request_fingerprint=fp,
                original_status=200,
                original_body=body,
                usage_event_id=event.id,
            )
        )
        db.commit()
        return 200, body


class QuotaExceeded(HTTPException):
    pass
