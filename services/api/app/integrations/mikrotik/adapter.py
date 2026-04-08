"""RouterOS adapter backed by the low-level MikroTik API client."""

from __future__ import annotations

from typing import Any

from app.integrations.mikrotik.client import MikroTikClient
from app.integrations.mikrotik.commands import (
    normalize_mac,
    parse_active_session,
    parse_system_resource,
)
from app.integrations.mikrotik.protocol import MikroTikHotspotPort


def _duration_to_routeros(seconds: int | None) -> str | None:
    if not seconds or seconds <= 0:
        return None
    remaining = int(seconds)
    parts: list[str] = []
    weeks, remaining = divmod(remaining, 604800)
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, remaining = divmod(remaining, 60)
    if weeks:
        parts.append(f"{weeks}w")
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if remaining or not parts:
        parts.append(f"{remaining}s")
    return "".join(parts)


class RouterOSAdapter(MikroTikHotspotPort):
    """Production-oriented facade over RouterOS binary API commands used by ESN."""

    def __init__(self, client: MikroTikClient) -> None:
        self._client = client

    async def test_connection(self) -> bool:
        resources = await self.fetch_system_resources()
        return bool(resources)

    async def fetch_system_resources(self) -> dict[str, Any]:
        response = await self._client.call(
            "/system/resource/print",
            attributes={
                ".proplist": "cpu-load,free-memory,total-memory,uptime,board-name,version,architecture-name",
            },
        )
        row = response.rows[0] if response.rows else {}
        return parse_system_resource(row)

    async def fetch_active_sessions(self) -> list[dict[str, Any]]:
        response = await self._client.call(
            "/ip/hotspot/active/print",
            attributes={".proplist": ".id,user,mac-address,address,uptime,bytes-in,bytes-out,server"},
        )
        return [parse_active_session(row) for row in response.rows if normalize_mac(row.get("mac-address"))]

    async def disconnect_hotspot_user(self, *, session_id: str | None = None, mac: str | None = None) -> bool:
        ids: list[str] = []
        if session_id:
            ids = [session_id]
        elif mac:
            response = await self._client.call(
                "/ip/hotspot/active/print",
                attributes={".proplist": ".id,mac-address"},
                queries=[f"mac-address={normalize_mac(mac)}"],
            )
            ids = [row.get(".id", "") for row in response.rows if row.get(".id")]
        changed = False
        for item_id in ids:
            await self._client.call("/ip/hotspot/active/remove", attributes={".id": item_id})
            changed = True
        return changed

    async def block_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        await self._set_ip_binding(mac=mac, binding_type="blocked", comment=f"esn:block:{list_name}")

    async def unblock_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        _ = list_name
        await self._remove_ip_binding(mac=mac, expected_types={"blocked"})

    async def whitelist_mac(self, *, mac: str, note: str | None = None) -> None:
        comment = "esn:whitelist"
        if note:
            comment = f"{comment}:{note}"
        await self._set_ip_binding(mac=mac, binding_type="bypassed", comment=comment)

    async def remove_whitelist_mac(self, *, mac: str) -> None:
        await self._remove_ip_binding(mac=mac, expected_types={"bypassed"})

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
        await self._ensure_hotspot_profile(profile_name=profile_name, rate_limit=rate_limit)
        attrs: dict[str, Any] = {
            "name": username,
            "password": password,
            "mac-address": normalize_mac(mac),
            "profile": profile_name,
            "comment": comment or "esn-managed hotspot user",
            "disabled": False,
        }
        if server:
            attrs["server"] = server
        limit_uptime = _duration_to_routeros(limit_uptime_seconds)
        if limit_uptime:
            attrs["limit-uptime"] = limit_uptime
        existing = await self._find_hotspot_user(username=username)
        if existing:
            await self._client.call("/ip/hotspot/user/set", attributes={".id": existing[".id"], **attrs})
            user_id = existing[".id"]
        else:
            created = await self._client.call("/ip/hotspot/user/add", attributes=attrs)
            user_id = created.done.get("ret") or username
        return {
            "id": user_id,
            "username": username,
            "mac_address": normalize_mac(mac),
            "profile_name": profile_name,
            "server": server,
            "limit_uptime": limit_uptime,
            "rate_limit": rate_limit,
        }

    async def remove_hotspot_user(self, *, username: str) -> bool:
        existing = await self._find_hotspot_user(username=username)
        if not existing:
            return False
        await self._client.call("/ip/hotspot/user/remove", attributes={".id": existing[".id"]})
        return True

    async def _find_ip_binding(self, mac: str) -> dict[str, str] | None:
        response = await self._client.call(
            "/ip/hotspot/ip-binding/print",
            attributes={".proplist": ".id,mac-address,type,comment"},
            queries=[f"mac-address={normalize_mac(mac)}"],
        )
        return response.rows[0] if response.rows else None

    async def _set_ip_binding(self, *, mac: str, binding_type: str, comment: str) -> None:
        norm = normalize_mac(mac)
        existing = await self._find_ip_binding(norm)
        attrs = {
            "mac-address": norm,
            "type": binding_type,
            "comment": comment,
            "disabled": False,
        }
        if existing:
            await self._client.call("/ip/hotspot/ip-binding/set", attributes={".id": existing[".id"], **attrs})
            return
        await self._client.call("/ip/hotspot/ip-binding/add", attributes=attrs)

    async def _remove_ip_binding(self, *, mac: str, expected_types: set[str]) -> None:
        existing = await self._find_ip_binding(mac)
        if not existing or existing.get("type") not in expected_types:
            return
        await self._client.call("/ip/hotspot/ip-binding/remove", attributes={".id": existing[".id"]})

    async def _ensure_hotspot_profile(self, *, profile_name: str, rate_limit: str | None) -> None:
        existing = await self._client.call(
            "/ip/hotspot/user/profile/print",
            attributes={".proplist": ".id,name,rate-limit,shared-users,status-autorefresh"},
            queries=[f"name={profile_name}"],
        )
        attrs: dict[str, Any] = {
            "name": profile_name,
            "shared-users": 1,
            "status-autorefresh": "1m",
        }
        if rate_limit:
            attrs["rate-limit"] = rate_limit
        if existing.rows:
            await self._client.call("/ip/hotspot/user/profile/set", attributes={".id": existing.rows[0][".id"], **attrs})
        else:
            await self._client.call("/ip/hotspot/user/profile/add", attributes=attrs)

    async def _find_hotspot_user(self, *, username: str) -> dict[str, str] | None:
        response = await self._client.call(
            "/ip/hotspot/user/print",
            attributes={".proplist": ".id,name,profile,mac-address,server,limit-uptime"},
            queries=[f"name={username}"],
        )
        return response.rows[0] if response.rows else None


__all__ = ["RouterOSAdapter"]
