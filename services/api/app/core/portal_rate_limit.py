"""Legacy portal rate-limit helpers (tests); production uses ``app.core.rate_limit``."""

from __future__ import annotations

from collections.abc import Callable

from starlette.requests import Request

from app.core.deps import get_client_ip
from app.core.rate_limit.limiter import check_portal_limit


async def check_portal_rate_limit(*, client_key: str, scope: str) -> None:
    action = scope if scope in ("redeem", "pay", "status") else "status"
    await check_portal_limit(action=action, site_slug="_global", client_ip=client_key)


def require_portal_rate_limit(scope: str) -> Callable[..., None]:
    async def _dep(request: Request) -> None:
        ip = await get_client_ip(request) or "unknown"
        await check_portal_rate_limit(client_key=ip, scope=scope)

    return _dep
