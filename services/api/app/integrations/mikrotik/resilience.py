from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.config import settings
from app.integrations.mikrotik.errors import MikrotikIntegrationError
from app.integrations.mikrotik.protocol import MikroTikHotspotPort

T = TypeVar("T")


def _classify(exc: BaseException) -> tuple[str, bool]:
    if isinstance(exc, MikrotikIntegrationError):
        return exc.code, exc.retryable
    if isinstance(exc, NotImplementedError):
        return "not_implemented", False
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout", True
    if isinstance(exc, TimeoutError):  # pragma: no cover — py3.11+
        return "timeout", True
    if isinstance(exc, (ConnectionError, OSError)):
        return "network", True
    return "adapter_error", True


class ResilientMikroTikAdapter:
    """Timeout + bounded retries around a real ``MikroTikHotspotPort`` implementation."""

    def __init__(self, inner: MikroTikHotspotPort) -> None:
        self._inner = inner
        self._timeout = settings.mikrotik_command_timeout_seconds
        self._retries = settings.mikrotik_max_retries

    async def _run(self, op: str, fn: Callable[[], Awaitable[T]]) -> T:
        last: BaseException | None = None
        for attempt in range(self._retries + 1):
            try:
                return await asyncio.wait_for(fn(), timeout=self._timeout)
            except MikrotikIntegrationError:
                raise
            except Exception as e:
                last = e
                code, retryable = _classify(e)
                if not retryable or attempt >= self._retries:
                    raise MikrotikIntegrationError(str(e), code=code, retryable=retryable) from e
                await asyncio.sleep(0.25 * (2**attempt))
        raise MikrotikIntegrationError(str(last), code="unknown", retryable=True) from last

    async def test_connection(self) -> bool:
        return await self._run("test_connection", self._inner.test_connection)

    async def fetch_system_resources(self) -> dict[str, Any]:
        return await self._run("fetch_system_resources", self._inner.fetch_system_resources)

    async def fetch_active_sessions(self) -> list[dict[str, Any]]:
        return await self._run("fetch_active_sessions", self._inner.fetch_active_sessions)

    async def disconnect_hotspot_user(self, *, session_id: str | None = None, mac: str | None = None) -> bool:
        return await self._run(
            "disconnect_hotspot_user",
            lambda: self._inner.disconnect_hotspot_user(session_id=session_id, mac=mac),
        )

    async def block_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        await self._run("block_mac", lambda: self._inner.block_mac(mac=mac, list_name=list_name))

    async def unblock_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        await self._run("unblock_mac", lambda: self._inner.unblock_mac(mac=mac, list_name=list_name))

    async def whitelist_mac(self, *, mac: str, note: str | None = None) -> None:
        await self._run("whitelist_mac", lambda: self._inner.whitelist_mac(mac=mac, note=note))

    async def remove_whitelist_mac(self, *, mac: str) -> None:
        await self._run("remove_whitelist_mac", lambda: self._inner.remove_whitelist_mac(mac=mac))

    async def ensure_hotspot_user(
        self,
        *,
        username: str,
        password: str,
        mac: str,
        profile_name: str,
        server: str | None,
        comment: str | None = None,
        limit_uptime_seconds: int | None = None,
        rate_limit: str | None = None,
    ) -> dict[str, Any]:
        return await self._run(
            "ensure_hotspot_user",
            lambda: self._inner.ensure_hotspot_user(
                username=username,
                password=password,
                mac=mac,
                profile_name=profile_name,
                server=server,
                comment=comment,
                limit_uptime_seconds=limit_uptime_seconds,
                rate_limit=rate_limit,
            ),
        )

    async def remove_hotspot_user(self, *, username: str) -> bool:
        return await self._run("remove_hotspot_user", lambda: self._inner.remove_hotspot_user(username=username))
