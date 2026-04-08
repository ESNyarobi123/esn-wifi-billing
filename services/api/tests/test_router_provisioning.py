from __future__ import annotations

import io
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.modules.routers.provisioning_service import RouterProvisioningOptions, build_router_provisioning_package


@pytest.mark.asyncio
async def test_build_router_provisioning_package_contains_expected_files():
    site = SimpleNamespace(id=uuid.uuid4(), name="Headquarters", slug="hq")
    router = SimpleNamespace(id=uuid.uuid4(), name="Cloudnix Net")
    branding = SimpleNamespace(
        primary_color="#0EA5E9",
        welcome_message="Welcome to ESN WiFi",
        support_phone="+255700000000",
        logo_url="https://cdn.example.com/logo.png",
    )
    package = build_router_provisioning_package(
        router=router,
        site=site,
        branding=branding,
        public_settings={
            "company_name": {"name": "ESN WiFi"},
            "support_email": {"email": "support@esn.local"},
        },
        options=RouterProvisioningOptions(
            portal_base_url="https://wifi.example.com",
            api_base_url="https://api.example.com",
            dns_name="login.example.com",
            extra_walled_garden_hosts=("checkout.example.com",),
        ),
    )

    assert package.filename.endswith(".zip")
    assert package.portal_url == "https://wifi.example.com/hq"
    assert "checkout.example.com" in package.walled_garden_hosts

    with zipfile.ZipFile(io.BytesIO(package.payload)) as archive:
        names = set(archive.namelist())
        assert "README.txt" in names
        assert "router-provisioning.rsc" in names
        assert "hotspot-files/login.html" in names
        assert "hotspot-files/api" in names
        script = archive.read("router-provisioning.rsc").decode()
        login_html = archive.read("hotspot-files/login.html").decode()
        readme = archive.read("README.txt").decode()
        logo_svg = archive.read("hotspot-files/logo.svg").decode()

    assert "https://wifi.example.com/hq" in script
    assert "https://api.example.com" in script
    assert "checkout.example.com" in script
    assert 'name="hs_mac"' in login_html
    assert "Generated ESN hotspot logo" in logo_svg
    assert "HotSpot HTML directory" in readme


@pytest.mark.asyncio
async def test_router_provisioning_endpoint_returns_zip():
    from app.core.deps import get_current_user, get_current_user_id, get_db_session, get_user_permissions
    from app.main import app

    router_id = uuid.uuid4()
    site_id = uuid.uuid4()
    router_row = SimpleNamespace(id=router_id, site_id=site_id, name="Cloudnix Net", status="active")
    site_row = SimpleNamespace(id=site_id, name="Headquarters", slug="hq", status="active")
    branding_row = SimpleNamespace(
        site_id=site_id,
        primary_color="#0EA5E9",
        welcome_message="Welcome to ESN WiFi",
        support_phone="+255700000000",
        logo_url=None,
    )
    settings_rows = [
        SimpleNamespace(key="company_name", value={"name": "ESN WiFi"}),
        SimpleNamespace(key="support_email", value={"email": "support@esn.local"}),
    ]

    class _Res:
        def __init__(self, *, scalar_one_or_none=None, scalars_list=None):
            self._son = scalar_one_or_none
            self._sl = scalars_list or []

        def scalar_one_or_none(self):
            return self._son

        def scalars(self):
            return self

        def all(self):
            return self._sl

    class _Sess:
        def __init__(self) -> None:
            self.n = 0

        async def execute(self, _stmt):
            self.n += 1
            if self.n == 1:
                return _Res(scalar_one_or_none=router_row)
            if self.n == 2:
                return _Res(scalar_one_or_none=site_row)
            if self.n == 3:
                return _Res(scalar_one_or_none=branding_row)
            return _Res(scalars_list=settings_rows)

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    async def fake_db():
        yield _Sess()

    async def fake_uid() -> uuid.UUID:
        return uuid.uuid4()

    async def fake_user():
        return SimpleNamespace(id=uuid.uuid4(), roles=[], email="admin@esn.local", full_name="Admin", is_active=True)

    async def fake_perms():
        return {"routers:write"}

    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_current_user_id] = fake_uid
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_user_permissions] = fake_perms
    try:
        transport = ASGITransport(app=app)
        with patch("app.api.v1.routes.router_mgmt.record_audit", new=AsyncMock()):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    f"/api/v1/routers/{router_id}/provisioning-package",
                    headers={"Authorization": "Bearer t", "Origin": "https://wifi.example.com"},
                    json={
                        "api_base_url": "https://api.example.com",
                        "dns_name": "login.example.com",
                    },
                )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")
        assert "attachment;" in response.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert "router-provisioning.rsc" in archive.namelist()
            assert "hotspot-files/login.html" in archive.namelist()
    finally:
        app.dependency_overrides.clear()
