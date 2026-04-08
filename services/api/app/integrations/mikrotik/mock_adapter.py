from __future__ import annotations

import random
import time
from typing import Any

from app.integrations.mikrotik.protocol import MikroTikHotspotPort


class MockMikroTikAdapter(MikroTikHotspotPort):
    """Deterministic-enough fake RouterOS for local dev and CI."""

    def __init__(self, router_label: str = "mock") -> None:
        self._router_label = router_label
        self._sessions: list[dict[str, Any]] = [
            {
                "id": "sess-1",
                "user": "demo-user",
                "mac_address": "AA:BB:CC:DD:EE:01",
                "ip_address": "10.5.0.10",
                "uptime_secs": 120,
                "bytes_up": 1024,
                "bytes_down": 50_000,
            }
        ]
        self._blocked: set[str] = set()
        self._whitelist: set[str] = set()
        self._users: dict[str, dict[str, Any]] = {}

    async def test_connection(self) -> bool:
        return True

    async def fetch_system_resources(self) -> dict[str, Any]:
        return {
            "cpu_load_percent": round(random.uniform(5, 40), 2),
            "free_memory_bytes": 500_000_000,
            "total_memory_bytes": 1_000_000_000,
            "uptime_seconds": int(time.time()) % 86_400,
            "board_name": f"Mock-{self._router_label}",
        }

    async def fetch_active_sessions(self) -> list[dict[str, Any]]:
        return list(self._sessions)

    async def disconnect_hotspot_user(self, *, session_id: str | None = None, mac: str | None = None) -> bool:
        before = len(self._sessions)
        if session_id:
            self._sessions = [s for s in self._sessions if s.get("id") != session_id]
        elif mac:
            self._sessions = [s for s in self._sessions if s.get("mac_address") != mac]
        return len(self._sessions) != before

    async def block_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        _ = list_name
        self._blocked.add(mac.upper())

    async def unblock_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        _ = list_name
        self._blocked.discard(mac.upper())

    async def whitelist_mac(self, *, mac: str, note: str | None = None) -> None:
        _ = note
        self._whitelist.add(mac.upper())

    async def remove_whitelist_mac(self, *, mac: str) -> None:
        self._whitelist.discard(mac.upper())

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
        user = {
            "username": username,
            "password": password,
            "mac": mac.upper(),
            "profile_name": profile_name,
            "server": server,
            "comment": comment,
            "limit_uptime_seconds": limit_uptime_seconds,
            "rate_limit": rate_limit,
        }
        self._users[username] = user
        return user

    async def remove_hotspot_user(self, *, username: str) -> bool:
        return self._users.pop(username, None) is not None
