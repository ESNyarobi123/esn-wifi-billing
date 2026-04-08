from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.integrations.mikrotik.adapter import RouterOSAdapter
from app.integrations.mikrotik.client import RouterOSResponse


@pytest.mark.asyncio
async def test_routeros_adapter_ensure_hotspot_user_creates_profile_and_user():
    calls: list[tuple[str, dict | None, list[str] | None]] = []

    async def fake_call(command: str, *, attributes=None, queries=None):
        calls.append((command, attributes, queries))
        if command == "/ip/hotspot/user/profile/print":
            return RouterOSResponse(rows=[], done={})
        if command == "/ip/hotspot/user/profile/add":
            return RouterOSResponse(rows=[], done={"ret": "*1"})
        if command == "/ip/hotspot/user/print":
            return RouterOSResponse(rows=[], done={})
        if command == "/ip/hotspot/user/add":
            return RouterOSResponse(rows=[], done={"ret": "*2"})
        raise AssertionError(f"unexpected command {command}")

    client = AsyncMock()
    client.call = fake_call
    adapter = RouterOSAdapter(client)

    result = await adapter.ensure_hotspot_user(
        username="esn-user",
        password="secret",
        mac="aa:bb:cc:dd:ee:ff",
        profile_name="esn-plan",
        server="hs-hq",
        comment="esn-grant:1",
        limit_uptime_seconds=3665,
        rate_limit="2M/4M",
    )

    assert result["id"] == "*2"
    assert result["profile_name"] == "esn-plan"
    assert result["limit_uptime"] == "1h1m5s"
    assert calls[0][0] == "/ip/hotspot/user/profile/print"
    assert calls[1][0] == "/ip/hotspot/user/profile/add"
    assert calls[1][1]["rate-limit"] == "2M/4M"
    assert calls[-1][0] == "/ip/hotspot/user/add"
    assert calls[-1][1]["mac-address"] == "AA:BB:CC:DD:EE:FF"
    assert calls[-1][1]["server"] == "hs-hq"
    assert calls[-1][1]["limit-uptime"] == "1h1m5s"


@pytest.mark.asyncio
async def test_routeros_adapter_disconnect_hotspot_user_by_mac_removes_matching_sessions():
    calls: list[tuple[str, dict | None, list[str] | None]] = []

    async def fake_call(command: str, *, attributes=None, queries=None):
        calls.append((command, attributes, queries))
        if command == "/ip/hotspot/active/print":
            return RouterOSResponse(rows=[{".id": "*A", "mac-address": "AA:BB:CC:DD:EE:01"}], done={})
        if command == "/ip/hotspot/active/remove":
            return RouterOSResponse(rows=[], done={})
        raise AssertionError(f"unexpected command {command}")

    client = AsyncMock()
    client.call = fake_call
    adapter = RouterOSAdapter(client)

    changed = await adapter.disconnect_hotspot_user(mac="aa:bb:cc:dd:ee:01")

    assert changed is True
    assert calls[0][0] == "/ip/hotspot/active/print"
    assert calls[0][2] == ["mac-address=AA:BB:CC:DD:EE:01"]
    assert calls[1][0] == "/ip/hotspot/active/remove"
    assert calls[1][1] == {".id": "*A"}
