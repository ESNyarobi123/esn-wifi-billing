"""Portal rate limit orchestration: Redis (distributed) or memory + fail-open/closed."""

from __future__ import annotations

import logging
import uuid
from typing import Literal

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.exceptions import RateLimitExceededError, ServiceUnavailableError
from app.core.rate_limit import keys as keyutil
from app.core.rate_limit.memory import memory_sliding_window_check
from app.core.rate_limit.redis_backend import redis_sliding_window_allow

logger = logging.getLogger(__name__)

PortalAction = Literal["redeem", "pay", "status"]

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def reset_redis_client_for_tests() -> None:
    global _redis_client
    _redis_client = None


def _limit_and_window(action: PortalAction) -> tuple[int, int]:
    if action == "redeem":
        return settings.portal_rate_limit_redeem_per_minute, settings.portal_rate_limit_redeem_window_seconds
    if action == "pay":
        return settings.portal_rate_limit_pay_per_minute, settings.portal_rate_limit_pay_window_seconds
    return settings.portal_rate_limit_status_per_minute, settings.portal_rate_limit_status_window_seconds


async def check_portal_limit(
    *,
    action: PortalAction,
    site_slug: str,
    client_ip: str | None,
    customer_id: uuid.UUID | None = None,
    voucher_code: str | None = None,
    phone: str | None = None,
    mac_address: str | None = None,
) -> None:
    limit, window_sec = _limit_and_window(action)
    if limit <= 0:
        return

    window_ms = max(1, window_sec) * 1000
    v_fp = keyutil.voucher_code_fingerprint(site_slug, voucher_code) if voucher_code else None
    p_fp = keyutil.phone_fingerprint(phone)
    m_fp = keyutil.mac_fingerprint(mac_address) if mac_address else None

    redis_key = keyutil.build_portal_rate_key(
        prefix=settings.portal_rate_limit_redis_key_prefix,
        action=action,
        site_slug=site_slug,
        client_ip=client_ip,
        customer_id=customer_id,
        voucher_fp=v_fp,
        phone_fp=p_fp if action == "pay" else None,
        mac_fp=m_fp if action == "status" and mac_address else None,
    )

    mem_key = keyutil.build_portal_rate_key(
        prefix="mem",
        action=action,
        site_slug=site_slug,
        client_ip=client_ip,
        customer_id=customer_id,
        voucher_fp=v_fp,
        phone_fp=p_fp if action == "pay" else None,
        mac_fp=m_fp if action == "status" and mac_address else None,
    )

    backend = settings.portal_rate_limit_backend.lower()
    if backend == "memory":
        await memory_sliding_window_check(key=mem_key, limit=limit, window_ms=float(window_ms))
        return

    try:
        ok = await redis_sliding_window_allow(_get_redis(), key=redis_key, limit=limit, window_ms=window_ms)
    except Exception as e:
        logger.warning(
            "portal rate limit Redis unavailable action=%s site=%s fail_open=%s err=%s",
            action,
            site_slug,
            settings.portal_rate_limit_redis_fail_open,
            e,
            exc_info=True,
        )
        if settings.portal_rate_limit_redis_fail_open:
            await memory_sliding_window_check(key=mem_key, limit=limit, window_ms=float(window_ms))
            return
        raise ServiceUnavailableError(
            "Rate limiting service temporarily unavailable; try again shortly",
        ) from e

    if not ok:
        raise RateLimitExceededError("Too many requests; try again shortly")
