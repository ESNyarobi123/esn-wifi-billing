from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions import AppError, RateLimitExceededError
from app.core.logging import configure_logging
from app.core.responses import err

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("DEBUG" if settings.api_env == "development" else "INFO")
    logger.info("API starting env=%s", settings.api_env)
    yield
    logger.info("API shutdown")


app = FastAPI(
    title="ESN WiFi Billing API",
    version="0.2.1",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Liveness/readiness."},
        {"name": "auth", "description": "JWT login and token refresh."},
        {"name": "portal", "description": "Public captive portal JSON (rate-limited)."},
        {"name": "payments", "description": "Intents, PSP webhooks (idempotent callbacks), mock completion."},
        {"name": "routers", "description": "NAS CRUD, live sessions, sync, block/unblock (RBAC)."},
        {"name": "customers", "description": "Customer directory."},
        {"name": "sessions", "description": "Stored hotspot sessions."},
        {"name": "vouchers", "description": "Batches and voucher lifecycle."},
        {"name": "analytics", "description": "Dashboard aggregates."},
        {"name": "settings", "description": "System settings."},
        {"name": "audit", "description": "Audit log read API."},
    ],
)

if settings.trusted_hosts_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceededError)
async def rate_limit_handler(_request: Request, exc: RateLimitExceededError) -> JSONResponse:
    body = err(exc.message, code=exc.code)
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    body = err(exc.message, code=exc.code, errors=getattr(exc, "errors", None))
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=err("Validation error", errors=exc.errors(), code="validation_error"),
    )


app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health_root():
    return {"status": "ok"}
