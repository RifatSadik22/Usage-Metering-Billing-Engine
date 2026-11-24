from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.billing import router as billing_router
from app.api.routes.generate import router as generate_router
from app.api.routes.health import router as health_router
from app.api.routes.usage import router as usage_router
from app.api.routes.webhooks import router as webhook_router
from app.core.logging import configure_logging

configure_logging()
app = FastAPI(title="Usage Metering & Billing Engine", version="1.0.0")

app.include_router(health_router)
app.include_router(usage_router)
app.include_router(generate_router)
app.include_router(billing_router)
app.include_router(webhook_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    clean = [{k: str(v) for k, v in error.items() if k != "ctx"} for error in errors]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": clean,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)
