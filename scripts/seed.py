from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_api_key
from app.models.models import Plan, Subscription, Tenant


def seed() -> dict:
    settings = get_settings()
    with SessionLocal.begin() as db:
        free = db.scalar(select(Plan).where(Plan.slug == "free"))
        if free is None:
            free = Plan(
                id=1,
                slug="free",
                name="Free",
                monthly_api_call_limit=1000,
                monthly_ai_token_limit=100000,
            )
            db.add(free)
        else:
            free.monthly_api_call_limit = 1000
            free.monthly_ai_token_limit = 100000
        pro = db.scalar(select(Plan).where(Plan.slug == "pro"))
        if pro is None:
            pro = Plan(
                id=2,
                slug="pro",
                name="Pro",
                monthly_api_call_limit=10000,
                monthly_ai_token_limit=1000000,
            )
            db.add(pro)
        else:
            pro.monthly_api_call_limit = 10000
            pro.monthly_ai_token_limit = 1000000
        db.flush()

        created = {}
        for name, key in (
            ("Demo Tenant A", settings.demo_tenant_a_api_key),
            ("Demo Tenant B", settings.demo_tenant_b_api_key),
        ):
            key_hash = hash_api_key(key)
            tenant = db.scalar(select(Tenant).where(Tenant.api_key_hash == key_hash))
            if tenant is None:
                tenant = Tenant(name=name, api_key_hash=key_hash)
                db.add(tenant)
                db.flush()
                db.add(Subscription(tenant_id=tenant.id, plan_id=free.id, status="free"))
            created[name] = str(tenant.id)
    return created


if __name__ == "__main__":
    print(seed())
