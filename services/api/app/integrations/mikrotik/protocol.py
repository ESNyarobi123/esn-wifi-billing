from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MikroTikHotspotPort(Protocol):
    async def test_connection(self) -> bool: ...

    async def fetch_system_resources(self) -> dict[str, Any]: ...

    async def fetch_active_sessions(self) -> list[dict[str, Any]]: ...

    async def disconnect_hotspot_user(self, *, session_id: str | None = None, mac: str | None = None) -> bool: ...

    async def block_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None: ...

    async def unblock_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None: ...

    async def whitelist_mac(self, *, mac: str, note: str | None = None) -> None: ...

    async def remove_whitelist_mac(self, *, mac: str) -> None: ...

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
    ) -> dict[str, Any]: ...

    async def remove_hotspot_user(self, *, username: str) -> bool: ...
