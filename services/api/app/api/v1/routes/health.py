from __future__ import annotations

from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.core.responses import err, ok
from app.db.session import engine

router = APIRouter()
log = get_logger(__name__)


async def check_database_connectivity() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        log.warning("readiness check failed: database: %s", e)
        return f"error: {e}"


async def check_redis_connectivity() -> str:
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
        return "ok"
    except Exception as e:
        log.warning("readiness check failed: redis: %s", e)
        return f"error: {e}"


@router.get("/health/live")
async def health_live():
    return ok({"status": "live", "service": "esn-wifi-api"}, message="OK")


@router.get("/health/ready")
async def health_ready(
    database: Annotated[str, Depends(check_database_connectivity)],
    redis_status: Annotated[str, Depends(check_redis_connectivity)],
):
    checks = {"database": database, "redis": redis_status}
    ready = database == "ok" and redis_status == "ok"
    body = {"ready": ready, "checks": checks}
    if not ready:
        log.error("service not ready checks=%s", checks)
        payload = err("Not ready", errors=body, code="not_ready")
        return JSONResponse(status_code=503, content=payload)
    return ok(body, message="OK")
