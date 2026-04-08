from __future__ import annotations

import io
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.modules.routers.provisioning_service import GeneratedProvisioningPackage


class _ScalarRes:
    def __init__(self, scalar_one_or_none=None, all_rows=None):
        self._scalar = scalar_one_or_none
        self._all_rows = all_rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._all_rows


def _package_bytes() -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "hello")
        archive.writestr("router-provisioning.rsc", "/system identity print")
        archive.writestr("hotspot-files/login.html", "<html>login</html>")
    return payload.getvalue()


@pytest.mark.asyncio
async def test_portal_access_status_resolves_customer_from_device_mac():
    from app.core.deps import get_db_session
    from app.main import app

    site_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    site = SimpleNamespace(id=site_id, name="HQ", slug="hq", status="active")
    device = SimpleNamespace(customer_id=customer_id)

    class _Sess:
        def __init__(self) -> None:
            self.n = 0

        async def execute(self, _stmt):
            self.n += 1
            if self.n == 1:
                return _ScalarRes(scalar_one_or_none=site)
            if self.n == 2:
                return _ScalarRes(scalar_one_or_none=device)
            raise AssertionError("unexpected execute call")

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    async def fake_db():
        yield _Sess()

    app.dependency_overrides[get_db_session] = fake_db
    try:
        transport = ASGITransport(app=app)
        with (
            patch("app.api.v1.routes.portal.subs_service.build_portal_access_status", new=AsyncMock(return_value={
                "site": {"id": str(site_id), "name": "HQ", "slug": "hq"},
                "customer_id": str(customer_id),
                "has_usable_access": True,
                "primary_access": None,
                "usable_grants": [],
            })),
            patch("app.api.v1.routes.portal.authorize_best_portal_access", new=AsyncMock(return_value={"available": True})),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/api/v1/portal/hq/access-status", params={"mac_address": "aa:bb:cc:dd:ee:01"})
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["customer_id"] == str(customer_id)
        assert body["data"]["resolved_by"] == "device_mac"
        assert body["data"]["authorization"]["available"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portal_pay_resolves_customer_from_known_device():
    from app.core.deps import get_db_session
    from app.main import app

    site_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    payment_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    site = SimpleNamespace(id=site_id, name="HQ", slug="hq", status="active")
    device = SimpleNamespace(customer_id=customer_id)

    class _Sess:
        async def execute(self, _stmt):
            return _ScalarRes(scalar_one_or_none=site)

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    async def fake_db():
        yield _Sess()

    app.dependency_overrides[get_db_session] = fake_db
    try:
        transport = ASGITransport(app=app)
        pay_mock = AsyncMock(
            return_value=(
                SimpleNamespace(
                    id=payment_id,
                    order_reference="ESN-1",
                    amount=1500,
                    currency="TZS",
                    payment_status="pending",
                    provider="clickpesa",
                    customer_id=customer_id,
                ),
                {"checkout_url": "https://checkout.example.com"},
            ),
        )
        with patch("app.api.v1.routes.portal.create_payment_intent", new=pay_mock):
            with patch(
                "app.api.v1.routes.portal.resolve_or_create_portal_customer",
                new=AsyncMock(return_value=(customer_id, "device_mac")),
            ) as resolve_mock:
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    response = await ac.post(
                        "/api/v1/portal/hq/pay",
                        json={
                            "plan_id": str(plan_id),
                            "amount": "1500",
                            "currency": "TZS",
                            "hotspot_context": {"mac_address": "aa:bb:cc:dd:ee:01"},
                        },
                    )
        assert response.status_code == 200
        resolve_mock.assert_awaited_once()
        assert pay_mock.await_args.kwargs["customer_id"] == customer_id
        assert pay_mock.await_args.kwargs["callback_url"] == "http://test/api/v1/payments/webhooks/clickpesa"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_or_create_portal_customer_creates_customer_and_device_binding():
    from app.modules.routers.hotspot_authorization_service import resolve_or_create_portal_customer

    site_id = uuid.uuid4()
    created_customer_id = uuid.uuid4()
    added: list[object] = []

    class _Sess:
        def __init__(self) -> None:
            self.n = 0

        async def execute(self, _stmt):
            self.n += 1
            if self.n == 1:
                return _ScalarRes(scalar_one_or_none=None)  # device lookup
            if self.n == 2:
                return _ScalarRes(all_rows=[])  # phone lookup
            if self.n == 3:
                return _ScalarRes(scalar_one_or_none=None)  # upsert device binding lookup
            raise AssertionError("unexpected execute call")

        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if getattr(obj, "phone", None) == "255712345678" and getattr(obj, "id", None) is None:
                    obj.id = created_customer_id

    session = _Sess()
    customer_id, resolved_by = await resolve_or_create_portal_customer(
        session,
        site_id=site_id,
        customer_id=None,
        mac_address="aa:bb:cc:dd:ee:01",
        phone="0712345678",
        email=None,
        full_name=None,
        hostname="Pixel-6a",
    )

    assert customer_id == created_customer_id
    assert resolved_by == "created_portal_customer"
    customer = next(obj for obj in added if getattr(obj, "phone", None) == "255712345678")
    device = next(obj for obj in added if getattr(obj, "mac_address", None) == "AA:BB:CC:DD:EE:01")
    assert customer.site_id == site_id
    assert customer.full_name == "WiFi Guest 5678"
    assert device.customer_id == created_customer_id
    assert device.hostname == "Pixel-6a"


@pytest.mark.asyncio
async def test_portal_redeem_resolves_customer_from_known_device():
    from app.core.deps import get_db_session
    from app.main import app

    site_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    site = SimpleNamespace(id=site_id, name="HQ", slug="hq", status="active")
    device = SimpleNamespace(customer_id=customer_id)

    class _Sess:
        def __init__(self) -> None:
            self.n = 0

        async def execute(self, _stmt):
            self.n += 1
            if self.n == 1:
                return _ScalarRes(scalar_one_or_none=site)
            if self.n == 2:
                return _ScalarRes(scalar_one_or_none=device)
            raise AssertionError("unexpected execute call")

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    async def fake_db():
        yield _Sess()

    app.dependency_overrides[get_db_session] = fake_db
    try:
        transport = ASGITransport(app=app)
        redeem_mock = AsyncMock(return_value={"success": True, "authorization": {"available": True}})
        with patch("app.api.v1.routes.portal.redeem_voucher", new=redeem_mock):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/portal/hq/redeem",
                    json={
                        "code": "ABC123",
                        "customer_id": None,
                        "hotspot_context": {"mac_address": "aa:bb:cc:dd:ee:01"},
                    },
                )
        assert response.status_code == 200
        assert redeem_mock.await_args.kwargs["customer_id"] == customer_id
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reconcile_access_lists_applies_router_state_and_skips_conflicts():
    from app.modules.routers import router_operations

    router_id = uuid.uuid4()
    admin = SimpleNamespace(id=uuid.uuid4())
    router = SimpleNamespace(id=router_id, name="R1", status="active")
    whitelist_row = SimpleNamespace(id=uuid.uuid4(), mac_address="AA:BB:CC:DD:EE:01", note="staff", created_at=1)
    blocked_conflict = SimpleNamespace(id=uuid.uuid4(), mac_address="AA:BB:CC:DD:EE:01", created_at=1)
    blocked_row = SimpleNamespace(id=uuid.uuid4(), mac_address="AA:BB:CC:DD:EE:02", created_at=2)

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _ScalarRes(all_rows=[blocked_conflict, blocked_row]),
            _ScalarRes(all_rows=[whitelist_row]),
        ],
    )
    adapter = SimpleNamespace(
        whitelist_mac=AsyncMock(),
        block_mac=AsyncMock(),
    )

    with (
        patch.object(router_operations, "get_router_or_error", new=AsyncMock(return_value=router)),
        patch.object(router_operations, "get_mikrotik_adapter", return_value=adapter),
        patch.object(router_operations, "record_audit", new=AsyncMock()) as audit_mock,
    ):
        result = await router_operations.execute_reconcile_access_lists(session, router_id=router_id, admin=admin)

    adapter.whitelist_mac.assert_awaited_once_with(mac="AA:BB:CC:DD:EE:01", note="staff")
    adapter.block_mac.assert_awaited_once_with(mac="AA:BB:CC:DD:EE:02")
    audit_mock.assert_awaited_once()
    assert result["whitelist_applied"] == 1
    assert result["blocked_applied"] == 1
    assert result["blocked_skipped"] == 1
    assert result["error_count"] == 0


@pytest.mark.asyncio
async def test_push_provisioning_package_uploads_imports_and_verifies():
    from app.integrations.mikrotik.client import RouterOSResponse
    from app.modules.routers.provisioning_push_service import push_provisioning_package_to_router

    router = SimpleNamespace(
        host="192.168.88.1",
        username="admin",
        password_encrypted="enc",
        api_port=8728,
        use_tls=False,
    )
    package = GeneratedProvisioningPackage(
        filename="pkg.zip",
        payload=_package_bytes(),
        script="/system identity print",
        html_directory="esn-hotspot-hq",
        portal_url="https://wifi.example.com/hq",
        api_url="https://api.example.com",
        dns_name="login.example.com",
        hotspot_server_name="esn-hotspot-hq",
        hotspot_profile_name="esn-profile-hq",
        walled_garden_hosts=(),
    )
    fake_client = SimpleNamespace(
        call=AsyncMock(),
        call_many=AsyncMock(
            return_value=[
                RouterOSResponse(rows=[{"board-name": "hAP ax2", "version": "7.17", "uptime": "1d2h"}], done={}),
                RouterOSResponse(rows=[{"name": "esn-profile-hq", "dns-name": "login.example.com"}], done={}),
                RouterOSResponse(rows=[{"name": "esn-hotspot-hq", "profile": "esn-profile-hq"}], done={}),
                RouterOSResponse(rows=[{"name": "login.example.com", "address": "10.10.10.1"}], done={}),
            ],
        ),
    )

    with (
        patch("app.modules.routers.provisioning_push_service.decrypt_secret", return_value="router-pass"),
        patch("app.modules.routers.provisioning_push_service._ftp_upload", return_value=["router-provisioning.rsc", "esn-hotspot-hq/login.html"]),
        patch("app.modules.routers.provisioning_push_service.MikroTikClient", return_value=fake_client),
    ):
        result = await push_provisioning_package_to_router(router=router, package=package)

    fake_client.call.assert_awaited_once_with("/import", attributes={"file-name": "router-provisioning.rsc"})
    assert result["uploaded_count"] == 2
    assert result["imported"] is True
    assert result["verification"]["router"]["board_name"] == "hAP ax2"


@pytest.mark.asyncio
async def test_push_provisioning_package_wraps_failures_as_service_unavailable():
    from app.core.exceptions import ServiceUnavailableError
    from app.modules.routers.provisioning_push_service import push_provisioning_package_to_router

    router = SimpleNamespace(
        host="192.168.88.1",
        username="admin",
        password_encrypted="enc",
        api_port=8728,
        use_tls=False,
    )
    package = GeneratedProvisioningPackage(
        filename="pkg.zip",
        payload=_package_bytes(),
        script="",
        html_directory="esn-hotspot-hq",
        portal_url="https://wifi.example.com/hq",
        api_url="https://api.example.com",
        dns_name="login.example.com",
        hotspot_server_name="esn-hotspot-hq",
        hotspot_profile_name="esn-profile-hq",
        walled_garden_hosts=(),
    )

    with (
        patch("app.modules.routers.provisioning_push_service.decrypt_secret", return_value="router-pass"),
        patch("app.modules.routers.provisioning_push_service._ftp_upload", side_effect=RuntimeError("ftp down")),
    ):
        with pytest.raises(ServiceUnavailableError, match="Provisioning push failed: ftp down"):
            await push_provisioning_package_to_router(router=router, package=package)
