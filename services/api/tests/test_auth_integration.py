from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_auth_me_unauthorized_without_token():
    """Protected /me without Authorization hits real deps — fails before DB access."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/auth/me")
    assert r.status_code == 401
    body = r.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_auth_me_with_dependency_override():
    """Exercise /auth/me success path without Postgres by overriding the current-user dependency."""
    from app.main import app
    from app.core.deps import get_current_user

    uid = uuid.uuid4()
    now = datetime.now(UTC)

    async def fake_current_user():
        return SimpleNamespace(
            id=uid,
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=now,
        )

    app.dependency_overrides[get_current_user] = fake_current_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/auth/me", headers={"Authorization": "Bearer placeholder"})
        assert r.status_code == 200
        payload = r.json()
        assert payload["success"] is True
        assert payload["data"]["email"] == "test@example.com"
        assert payload["data"]["full_name"] == "Test User"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_overview_forbidden_without_permissions():
    from datetime import UTC, datetime

    from app.main import app
    from app.core.deps import get_current_user, get_current_user_id

    uid = uuid.uuid4()
    now = datetime.now(UTC)

    async def fake_uid() -> uuid.UUID:
        return uid

    async def fake_user():
        return SimpleNamespace(
            id=uid,
            email="plain@example.com",
            full_name="Plain User",
            is_active=True,
            created_at=now,
            roles=[],
        )

    app.dependency_overrides[get_current_user_id] = fake_uid
    app.dependency_overrides[get_current_user] = fake_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/analytics/overview", headers={"Authorization": "Bearer token"})
        assert r.status_code == 403
        err_body = r.json()
        assert err_body["success"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portal_plans_not_found_with_fake_db():
    """Portal plans returns 404 when site slug is unknown — mock DB session so no PostgreSQL."""
    from app.main import app
    from app.core.deps import get_db_session

    class _FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

        def scalar_one_or_none(self):
            return None

    class _FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def execute(self, _stmt):  # noqa: ANN001
            return _FakeResult()

    async def fake_db():
        yield _FakeSession()

    app.dependency_overrides[get_db_session] = fake_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/portal/hq/plans")
        assert r.status_code == 404
        body = r.json()
        assert body["success"] is False
    finally:
        app.dependency_overrides.clear()
