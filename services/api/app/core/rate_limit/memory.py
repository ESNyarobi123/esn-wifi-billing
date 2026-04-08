"""In-process sliding-window limiter (single instance / tests / fallback)."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from app.core.exceptions import RateLimitExceededError

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


def _now_ms() -> float:
    return time.monotonic() * 1000.0


async def memory_sliding_window_check(*, key: str, limit: int, window_ms: float) -> None:
    if limit <= 0:
        return
    now = _now_ms()
    async with _lock:
        window = _buckets[key]
        while window and now - window[0] > window_ms:
            window.pop(0)
        if len(window) >= limit:
            raise RateLimitExceededError("Too many requests; try again shortly")
        window.append(now)


def memory_sliding_window_reset() -> None:
    """Test helper: clear buckets."""
    _buckets.clear()
