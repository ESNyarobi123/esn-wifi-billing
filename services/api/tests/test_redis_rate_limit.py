"""Portal rate limit: Redis code paths (mocked eval), key scoping, fail-open / fail-closed."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import RateLimitExceededError, ServiceUnavailableError
from app.core.rate_limit import keys as keyutil
from app.core.rate_limit.limiter import check_portal_limit, reset_redis_client_for_tests
from app.core.rate_limit.redis_backend import redis_sliding_window_allow


@pytest.mark.asyncio
async def test_redis_sliding_window_interprets_lua_result():
    """Production Redis runs Lua; here we assert 1/0 from ``eval`` maps to allow/deny."""
    client = AsyncMock()
    client.eval = AsyncMock(side_effect=[1, 1, 1, 0])
    key = "test:rl:1"
    for _ in range(3):
        assert await redis_sliding_window_allow(client, key=key, limit=3, window_ms=60_000) is True
    assert await redis_sliding_window_allow(client, key=key, limit=3, window_ms=60_000) is False


@pytest.mark.asyncio
async def test_portal_limit_redis_different_keys_independent(monkeypatch):
    """Same IP/customer/voucher but different site_slug → different Redis keys → separate counters."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "portal_rate_limit_backend", "redis")
    monkeypatch.setattr(settings, "portal_rate_limit_redeem_per_minute", 1)
    monkeypatch.setattr("app.core.rate_limit.limiter._get_redis", lambda: AsyncMock())

    counts: dict[str, int] = {}

    async def fake_allow(_client, *, key: str, limit: int, window_ms: int) -> bool:
        counts[key] = counts.get(key, 0) + 1
        return counts[key] <= limit

    monkeypatch.setattr("app.core.rate_limit.limiter.redis_sliding_window_allow", fake_allow)

    cid = uuid.uuid4()
    await check_portal_limit(
        action="redeem",
        site_slug="a",
        client_ip="1.1.1.1",
        customer_id=cid,
        voucher_code="X",
    )
    with pytest.raises(RateLimitExceededError):
        await check_portal_limit(
            action="redeem",
            site_slug="a",
            client_ip="1.1.1.1",
            customer_id=cid,
            voucher_code="X",
        )
    await check_portal_limit(
        action="redeem",
        site_slug="b",
        client_ip="1.1.1.1",
        customer_id=cid,
        voucher_code="X",
    )


@pytest.mark.asyncio
async def test_rate_limit_429_shape_unchanged(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "portal_rate_limit_backend", "redis")
    monkeypatch.setattr(settings, "portal_rate_limit_pay_per_minute", 1)
    monkeypatch.setattr("app.core.rate_limit.limiter._get_redis", lambda: AsyncMock())

    n = 0

    async def fake_allow(_c, *, key: str, limit: int, window_ms: int) -> bool:
        nonlocal n
        n += 1
        return n <= limit

    monkeypatch.setattr("app.core.rate_limit.limiter.redis_sliding_window_allow", fake_allow)

    await check_portal_limit(
        action="pay",
        site_slug="hq",
        client_ip="9.9.9.9",
        phone="+255700000001",
    )
    with pytest.raises(RateLimitExceededError) as ei:
        await check_portal_limit(
            action="pay",
            site_slug="hq",
            client_ip="9.9.9.9",
            phone="+255700000001",
        )
    assert ei.value.code == "rate_limit_exceeded"
    assert ei.value.status_code == 429


@pytest.mark.asyncio
async def test_redis_fail_open_falls_back_to_memory(monkeypatch):
    from app.core.config import settings
    from app.core.rate_limit.memory import memory_sliding_window_reset

    monkeypatch.setattr(settings, "portal_rate_limit_backend", "redis")
    monkeypatch.setattr(settings, "portal_rate_limit_redis_fail_open", True)
    monkeypatch.setattr(settings, "portal_rate_limit_pay_per_minute", 1)

    def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.rate_limit.limiter._get_redis", boom)
    memory_sliding_window_reset()
    await check_portal_limit(action="pay", site_slug="hq", client_ip="8.8.8.8")
    with pytest.raises(RateLimitExceededError):
        await check_portal_limit(action="pay", site_slug="hq", client_ip="8.8.8.8")


@pytest.mark.asyncio
async def test_redis_fail_closed_503(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "portal_rate_limit_backend", "redis")
    monkeypatch.setattr(settings, "portal_rate_limit_redis_fail_open", False)

    def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.rate_limit.limiter._get_redis", boom)
    with pytest.raises(ServiceUnavailableError) as ei:
        await check_portal_limit(action="pay", site_slug="hq", client_ip="8.8.8.8")
    assert ei.value.status_code == 503
    assert ei.value.code == "service_unavailable"


def test_key_includes_site_and_normalized_ip():
    slug = keyutil.normalize_site_slug(" MySite ")
    k = keyutil.build_portal_rate_key(
        prefix="p",
        action="redeem",
        site_slug=" MySite ",
        client_ip="192.168.0.1",
        customer_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
        voucher_fp="abc123",
    )
    assert slug in k
    assert "redeem" in k
    assert "192.168.0.1" in k
    assert "550e8400-e29b-41d4-a716-446655440000" in k


@pytest.fixture(autouse=True)
def _reset_redis_singleton():
    reset_redis_client_for_tests()
    yield
    reset_redis_client_for_tests()
