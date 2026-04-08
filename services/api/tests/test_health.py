import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.routes.health import check_database_connectivity, check_redis_connectivity
from app.main import app


@pytest.mark.asyncio
async def test_health_live():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["status"] == "live"


@pytest.mark.asyncio
async def test_health_ready_dependency_overrides():
    async def ok_db() -> str:
        return "ok"

    async def ok_redis() -> str:
        return "ok"

    app.dependency_overrides[check_database_connectivity] = ok_db
    app.dependency_overrides[check_redis_connectivity] = ok_redis
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["ready"] is True
    finally:
        app.dependency_overrides.clear()
