import pytest

from app.integrations.mikrotik.mock_adapter import MockMikroTikAdapter


@pytest.mark.asyncio
async def test_mock_sessions_and_disconnect():
    ad = MockMikroTikAdapter("t")
    assert await ad.test_connection() is True
    rows = await ad.fetch_active_sessions()
    assert len(rows) >= 1
    mac = rows[0]["mac_address"]
    assert await ad.disconnect_hotspot_user(mac=mac) is True
    rows2 = await ad.fetch_active_sessions()
    assert all(r["mac_address"] != mac for r in rows2)
