"""Business-flow tests using mocks (no Postgres / MikroTik / payment providers required)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.enums import AccessGrantStatus, PaymentStatus, PlanType, VoucherStatus
from app.modules.payments import service as pay_service
from app.modules.subscriptions import service as subs_service
from app.modules.vouchers.redemption import redeem_voucher


def _plan(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        name="Test Plan",
        plan_type=PlanType.time.value,
        duration_seconds=3600,
        is_active=True,
        price_amount=1000,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _voucher(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        code="ABC",
        status=VoucherStatus.unused.value,
        plan_id=uuid.uuid4(),
        pin=None,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        assigned_customer_id=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_redeem_voucher_expired_raises():
    plan = _plan()
    v = _voucher(plan_id=plan.id, expires_at=datetime.now(UTC) - timedelta(hours=1))
    session = MagicMock()
    session.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: v))
    session.flush = AsyncMock()
    from app.core.exceptions import ValidationAppError

    with pytest.raises(ValidationAppError, match="(?i)expired"):
        await redeem_voucher(
            session,
            site_id=uuid.uuid4(),
            code="ANY",
            pin=None,
            customer_id=uuid.uuid4(),
            actor_user_id=None,
            channel="portal",
        )


@pytest.mark.asyncio
async def test_redeem_voucher_already_used_same_customer_idempotent_payload():
    site_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    plan = _plan()
    v = _voucher(status=VoucherStatus.used.value, plan_id=plan.id, assigned_customer_id=cust_id)
    grant = SimpleNamespace(
        id=uuid.uuid4(),
        customer_id=cust_id,
        plan_id=plan.id,
        starts_at=datetime.now(UTC),
        ends_at=datetime.now(UTC) + timedelta(hours=1),
        site_id=site_id,
        status=AccessGrantStatus.active.value,
    )
    calls = iter(
        [
            SimpleNamespace(scalar_one_or_none=lambda: v),
            SimpleNamespace(scalar_one_or_none=lambda: plan),
            SimpleNamespace(scalar_one_or_none=lambda: grant),
            SimpleNamespace(scalar_one_or_none=lambda: plan),
        ],
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda _stmt: next(calls))

    with patch("app.modules.vouchers.redemption.subs_service.is_plan_offered_at_site", new=AsyncMock(return_value=True)):
        out = await redeem_voucher(
            session,
            site_id=site_id,
            code="USED-OK",
            pin=None,
            customer_id=cust_id,
            actor_user_id=None,
            channel="portal",
        )
    assert out["success"] is True
    assert out["idempotent"] is True


@pytest.mark.asyncio
async def test_redeem_voucher_used_wrong_customer_conflict():
    site_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    other = uuid.uuid4()
    plan = _plan()
    v = _voucher(status=VoucherStatus.used.value, plan_id=plan.id)
    grant = SimpleNamespace(customer_id=other, plan_id=plan.id, id=uuid.uuid4(), starts_at=datetime.now(UTC), ends_at=None, site_id=site_id, status="active")
    calls = iter(
        [
            SimpleNamespace(scalar_one_or_none=lambda: v),
            SimpleNamespace(scalar_one_or_none=lambda: plan),
            SimpleNamespace(scalar_one_or_none=lambda: grant),
        ],
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda _stmt: next(calls))
    from app.core.exceptions import ConflictError

    with patch("app.modules.vouchers.redemption.subs_service.is_plan_offered_at_site", new=AsyncMock(return_value=True)):
        with pytest.raises(ConflictError):
            await redeem_voucher(
                session,
                site_id=site_id,
                code="USED-BAD",
                pin=None,
                customer_id=cust_id,
                actor_user_id=None,
                channel="portal",
            )


@pytest.mark.asyncio
async def test_activate_payment_idempotent_replay():
    cust_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    pay_id = uuid.uuid4()
    pay = SimpleNamespace(
        id=pay_id,
        payment_status=PaymentStatus.success.value,
        customer_id=cust_id,
        plan_id=plan_id,
        site_id=uuid.uuid4(),
        voucher_batch_id=None,
        provider="mock",
        order_reference="O1",
        amount=1000,
        currency="TZS",
    )
    session = MagicMock()
    session.add = MagicMock()
    with (
        patch.object(
            subs_service,
            "ensure_payment_activation_grant",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ) as ensure,
        patch.object(pay_service, "_sync_voucher_batch_after_payment", new=AsyncMock()),
    ):
        out = await pay_service.activate_access_after_successful_payment(session, pay, provider_payload=None)
    ensure.assert_awaited_once()
    assert out["idempotent_replay"] is True
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_payment_first_success_creates_event_and_grant():
    cust_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    pay_id = uuid.uuid4()
    pay = SimpleNamespace(
        id=pay_id,
        payment_status=PaymentStatus.pending.value,
        customer_id=cust_id,
        plan_id=plan_id,
        site_id=uuid.uuid4(),
        voucher_batch_id=None,
        provider="mock",
        order_reference="O-NEW",
        amount=1000,
        currency="TZS",
    )
    session = MagicMock()
    session.add = MagicMock()
    fake_grant = SimpleNamespace(id=uuid.uuid4())
    with (
        patch.object(
            subs_service,
            "grant_access_from_payment",
            new=AsyncMock(return_value=fake_grant),
        ) as gg,
        patch.object(pay_service, "_sync_voucher_batch_after_payment", new=AsyncMock()),
        patch("app.modules.notifications.service.notify_customer_payment", new=AsyncMock()),
    ):
        out = await pay_service.activate_access_after_successful_payment(session, pay, provider_payload={"k": 1})
    assert out["idempotent_replay"] is False
    assert pay.payment_status == PaymentStatus.success.value
    gg.assert_awaited_once()
    assert session.add.called


@pytest.mark.asyncio
async def test_apply_payment_failed_ignores_after_success():
    pay = SimpleNamespace(
        id=uuid.uuid4(),
        payment_status=PaymentStatus.success.value,
        customer_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        site_id=None,
        voucher_batch_id=None,
        provider="mock",
        order_reference="O2",
        amount=1,
        currency="TZS",
    )
    session = MagicMock()
    session.add = MagicMock()
    await pay_service.apply_payment_failed(session, pay, reason={"x": 1})
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_compute_grant_entitlement_expired_window():
    plan = _plan()
    g = SimpleNamespace(
        status=AccessGrantStatus.active.value,
        starts_at=datetime.now(UTC) - timedelta(hours=2),
        ends_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    ent = subs_service.compute_grant_entitlement(grant=g, plan=plan, now=datetime.now(UTC))
    assert ent["is_usable"] is False
    assert ent["status"] == AccessGrantStatus.expired.value


@pytest.mark.asyncio
async def test_router_block_mac_records_audit():
    from unittest.mock import patch

    from app.modules.routers import router_operations

    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    rid = uuid.uuid4()
    admin = SimpleNamespace(id=uuid.uuid4())
    router = SimpleNamespace(id=rid, site_id=uuid.uuid4(), status="active", name="R1")
    with (
        patch.object(router_operations, "get_mikrotik_adapter") as gma,
        patch.object(router_operations, "get_router_or_error", new=AsyncMock(return_value=router)),
        patch.object(router_operations, "record_audit", new=AsyncMock()) as aud,
    ):
        mock_ad = MagicMock()
        mock_ad.block_mac = AsyncMock()
        gma.return_value = mock_ad
        out = await router_operations.execute_block_mac(session, router_id=rid, admin=admin, mac="aa:bb:cc:dd:ee:ff")
    aud.assert_awaited_once()
    assert out["action"] == "block_mac"
    assert out["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_router_disconnect_requires_permission():
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_current_user, get_current_user_id
    from app.main import app

    uid = uuid.uuid4()
    rid = uuid.uuid4()

    async def fake_uid() -> uuid.UUID:
        return uid

    async def fake_user():
        return SimpleNamespace(id=uid, roles=[], email="n@x.co", full_name="N", is_active=True)

    app.dependency_overrides[get_current_user_id] = fake_uid
    app.dependency_overrides[get_current_user] = fake_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/routers/{rid}/disconnect",
                headers={"Authorization": "Bearer t"},
                params={"mac": "AA:BB:CC:DD:EE:01"},
            )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portal_access_status_ok_with_fake_db():
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_db_session
    from app.main import app

    site_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    site = SimpleNamespace(
        id=site_id,
        name="HQ",
        slug="hq",
        timezone="Africa/Dar_es_Salaam",
        status="active",
    )
    cust = SimpleNamespace(id=cust_id, site_id=site_id)

    class _Res:
        def __init__(self, **kw):
            self._kw = kw

        def scalar_one_or_none(self):
            return self._kw.get("scalar_one_or_none")

        def scalars(self):
            return self

        def all(self):
            return self._kw.get("all", [])

    class _Grants:
        def scalars(self):
            return self

        def all(self):
            return []

    class _Sess:
        def __init__(self) -> None:
            self.n = 0

        async def execute(self, _stmt):
            self.n += 1
            if self.n == 1:
                return _Res(scalar_one_or_none=site)
            if self.n == 2:
                return _Res(scalar_one_or_none=cust)
            if self.n == 3:
                return _Res(scalar_one_or_none=site)
            if self.n == 4:
                return _Grants()
            return _Res(scalar_one_or_none=None)

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
            r = await ac.get(f"/api/v1/portal/hq/access-status?customer_id={cust_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "has_usable_access" in body["data"]
    finally:
        app.dependency_overrides.clear()
