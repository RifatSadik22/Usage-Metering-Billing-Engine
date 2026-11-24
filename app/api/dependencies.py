import re

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_api_key
from app.models.models import Tenant

API_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def get_authenticated_tenant(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Tenant:
    if not x_api_key or not API_KEY_PATTERN.fullmatch(x_api_key):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "A valid X-API-Key is required."}},
        )
    if db is None:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "SERVER_ERROR", "message": "Database unavailable."}},
        )
    candidate_hashes = list(db.scalars(select(Tenant)))
    for tenant in candidate_hashes:
        if verify_api_key(x_api_key, tenant.api_key_hash):
            return tenant
    raise HTTPException(
        status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key."}}
    )
