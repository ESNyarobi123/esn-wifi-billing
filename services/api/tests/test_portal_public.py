from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_portal_public_status_with_fake_db():
    from app.core.deps import get_db_session
    from app.main import app

    site_id = uuid.uuid4()
    site = SimpleNamespace(
        id=site_id,
        name="HQ",
        slug="hq",
        timezone="Africa/Dar_es_Salaam",
        status="active",
    )

    class _Res:
        def __init__(self, *, scalar_one_or_none=None, scalar_one=None):
            self._son = scalar_one_or_none
            self._so = scalar_one

        def scalar_one_or_none(self):
            return self._son

        def scalar_one(self):
            return self._so

    class _Sess:
        def __init__(self) -> None:
            self._n = 0

        async def execute(self, _stmt):
            self._n += 1
            if self._n == 1:
                return _Res(scalar_one_or_none=site)
            if self._n == 2:
                return _Res(scalar_one=3)
            return _Res(scalar_one=1)

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    async def fake_db():
        yield _Sess()

    app.dependency_overrides[get_db_session] = fake_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/portal/hq/status")
        assert r.status_code == 200
        payload = r.json()
        assert payload["success"] is True
        assert payload["data"]["routers"]["total"] == 3
        assert payload["data"]["routers"]["online"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portal_public_settings_with_fake_db():
    from app.core.deps import get_db_session
    from app.main import app

    site_id = uuid.uuid4()
    site = SimpleNamespace(
        id=site_id,
        name="HQ",
        slug="hq",
        timezone="Africa/Dar_es_Salaam",
        status="active",
    )

    row = SimpleNamespace(key="company_name", value={"name": "Demo"})

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
            self._n = 0

        async def execute(self, _stmt):
            self._n += 1
            if self._n == 1:
                return _Res(scalar_one_or_none=site)
            return _Res(scalars_list=[row])

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    async def fake_db():
        yield _Sess()

    app.dependency_overrides[get_db_session] = fake_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/portal/hq/settings")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["settings"]["company_name"] == {"name": "Demo"}
    finally:
        app.dependency_overrides.clear()
