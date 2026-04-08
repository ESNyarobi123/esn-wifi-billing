from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.security import decrypt_secret
from app.integrations.mikrotik.adapter import RouterOSAdapter
from app.integrations.mikrotik.client import MikroTikClient
from app.integrations.mikrotik.errors import MikrotikIntegrationError
from app.integrations.mikrotik.mock_adapter import MockMikroTikAdapter
from app.integrations.mikrotik.protocol import MikroTikHotspotPort
from app.integrations.mikrotik.resilience import ResilientMikroTikAdapter
from app.integrations.mikrotik.routeros_rest_stub import RouterOSRestAdapterStub
from app.modules.routers.models import Router


class _CredentialErrorAdapter:
    def __init__(self, message: str) -> None:
        self._message = message

    def _raise(self) -> None:
        raise MikrotikIntegrationError(self._message, code="credentials", retryable=False)

    async def test_connection(self) -> bool:
        self._raise()

    async def fetch_system_resources(self) -> dict[str, Any]:
        self._raise()

    async def fetch_active_sessions(self) -> list[dict[str, Any]]:
        self._raise()

    async def disconnect_hotspot_user(self, *, session_id: str | None = None, mac: str | None = None) -> bool:
        _ = (session_id, mac)
        self._raise()

    async def block_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        _ = (mac, list_name)
        self._raise()

    async def unblock_mac(self, *, mac: str, list_name: str = "esn_blocked") -> None:
        _ = (mac, list_name)
        self._raise()

    async def whitelist_mac(self, *, mac: str, note: str | None = None) -> None:
        _ = (mac, note)
        self._raise()

    async def remove_whitelist_mac(self, *, mac: str) -> None:
        _ = mac
        self._raise()

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
        _ = (username, password, mac, profile_name, server, comment, limit_uptime_seconds, rate_limit)
        self._raise()

    async def remove_hotspot_user(self, *, username: str) -> bool:
        _ = username
        self._raise()


def get_mikrotik_adapter(r: Router) -> MikroTikHotspotPort:
    if settings.mikrotik_use_mock:
        return MockMikroTikAdapter(router_label=r.name)
    if settings.mikrotik_use_routeros_rest_stub:
        inner: MikroTikHotspotPort = RouterOSRestAdapterStub(host=r.host, port=r.api_port, use_tls=r.use_tls)
    else:
        try:
            password = decrypt_secret(r.password_encrypted)
        except Exception as exc:  # noqa: BLE001
            inner = _CredentialErrorAdapter(f"Router credentials are not usable: {exc}")
        else:
            client = MikroTikClient(
                host=r.host,
                username=r.username,
                password=password,
                port=r.api_port,
                use_tls=r.use_tls,
            )
            inner = RouterOSAdapter(client)
    return ResilientMikroTikAdapter(inner)
