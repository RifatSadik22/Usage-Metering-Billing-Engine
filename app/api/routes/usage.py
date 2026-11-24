from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_tenant
from app.core.database import get_db
from app.models.models import Tenant
from app.services.meter_service import get_effective_subscription
from app.services.usage_service import get_usage

router = APIRouter()


@router.get("/usage")
def usage(
    tenant: Tenant = Depends(get_authenticated_tenant),
    db: Session = Depends(get_db),
):
    subscription, plan = get_effective_subscription(db, tenant.id)
    return get_usage(db, tenant, subscription, plan)
