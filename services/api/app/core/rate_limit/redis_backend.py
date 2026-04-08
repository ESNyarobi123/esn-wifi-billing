"""Atomic sliding-window rate limit using Redis ZSET + Lua."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local rid = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_ms)
local n = redis.call('ZCARD', key)
if n >= limit then
  return 0
end
redis.call('ZADD', key, now, rid)
redis.call('PEXPIRE', key, window_ms + 2000)
return 1
"""


async def redis_sliding_window_allow(
    client: Redis,
    *,
    key: str,
    limit: int,
    window_ms: int,
) -> bool:
    """Return True if request allowed, False if rate limited (atomic)."""
    if limit <= 0:
        return True
    now_ms = int(__import__("time").time() * 1000)
    rid = f"{now_ms}:{uuid.uuid4().hex}"
    try:
        allowed = await client.eval(SLIDING_WINDOW_LUA, 1, key, str(now_ms), str(window_ms), str(limit), rid)
    except Exception:
        logger.exception("redis rate limit eval failed key=%s", key)
        raise
    return int(allowed) == 1
