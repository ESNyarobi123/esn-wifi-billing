"""Placeholder RouterOS/HTTPS REST-style adapter — same method contract as ``RouterOSAdapter``; wire HTTP paths later."""

from __future__ import annotations

from typing import Any


class RouterOSRestAdapterStub:
    """Explicit stub for production checklist: swap in REST client without changing ``router_operations``."""

    def __init__(self, *, host: str, port: int, use_tls: bool) -> None:
        self._host = host
        self._port = port
        self._use_tls = use_tls

    async def test_connection(self) -> bool:
        raise NotImplementedError("RouterOSRestAdapterStub.test_connection — implement REST health check")

    async def fetch_system_resources(self) -> dict[str, Any]:
        raise NotImplementedError("RouterOSRestAdapterStub.fetch_system_resources")

    async def fetch_active_sessions(self) -> list[dict[str, Any]]:
        raise NotImplementedError("RouterOSRestAdapterStub.fetch_active_sessions")

    async def disconnect_hotspot_user(self, *, session_id: str | None = None, mac: str | None = None) -> bool:
        raise NotImplementedError("RouterOSRestAdapterStub.disconnect_hotspot_user")

    async def block_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        raise NotImplementedError("RouterOSRestAdapterStub.block_mac")

    async def unblock_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        raise NotImplementedError("RouterOSRestAdapterStub.unblock_mac")

    async def whitelist_mac(self, *, mac: str, note: str | None = None) -> None:
        raise NotImplementedError("RouterOSRestAdapterStub.whitelist_mac")

    async def remove_whitelist_mac(self, *, mac: str) -> None:
        raise NotImplementedError("RouterOSRestAdapterStub.remove_whitelist_mac")

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
        raise NotImplementedError("RouterOSRestAdapterStub.ensure_hotspot_user")

    async def remove_hotspot_user(self, *, username: str) -> bool:
        raise NotImplementedError("RouterOSRestAdapterStub.remove_hotspot_user")
