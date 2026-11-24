import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_tenant
from app.core.database import get_db
from app.models.models import Tenant
from app.schemas.generate import GenerateRequest
from app.services.meter_service import MeterService, QuotaExceeded, retry_after_seconds

router = APIRouter()
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,127}$")


@router.post("/generate")
def generate(
    request: Request,
    payload: GenerateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    tenant: Tenant = Depends(get_authenticated_tenant),
    db: Session = Depends(get_db),
):
    if not idempotency_key or not IDEMPOTENCY_PATTERN.fullmatch(idempotency_key):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_IDEMPOTENCY_KEY",
                    "message": (
                        "Idempotency-Key must be 6-128 characters using "
                        "letters, digits, ., _, :, or -."
                    ),
                }
            },
        )
    try:
        status, body = MeterService().generate(
            db, tenant, idempotency_key, payload.model_dump()
        )
        if status != 200:
            headers = {"Retry-After": str(retry_after_seconds())} if status == 429 else None
            return JSONResponse(status_code=status, content=body, headers=headers)
        return body
    except QuotaExceeded as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            headers={"Retry-After": str(retry_after_seconds())},
        )
