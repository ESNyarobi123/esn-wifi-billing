from __future__ import annotations

from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.enums import AccessGrantStatus, PaymentStatus


def test_webhook_dedupe_key_prefers_transaction_id():
    from app.integrations.payments.dedupe import compute_webhook_dedupe_key
    from app.integrations.payments.types import WebhookVerificationResult

    r = WebhookVerificationResult(
        signature_valid=True,
        provider_transaction_id="TX-123",
        normalized_outcome="success",
    )
    k = compute_webhook_dedupe_key(provider="clickpesa", payload={"x": 1}, result=r)
    assert k == "clickpesa:txn:TX-123"


@pytest.mark.asyncio
async def test_clickpesa_verify_without_checksum_key_normalizes(monkeypatch):
    from app.core.config import settings
    from app.integrations.payments.clickpesa import ClickPesaProvider

    monkeypatch.setattr(settings, "clickpesa_checksum_key", "")
    p = ClickPesaProvider()
    out = await p.verify_webhook(
        {
            "event": "PAYMENT RECEIVED",
            "data": {"orderReference": "O-1", "transactionId": "TX9", "status": "SUCCESS"},
        },
        {},
    )
    assert out.signature_valid is True
    assert out.normalized_outcome == "success"
    assert out.order_reference == "O-1"


@pytest.mark.asyncio
async def test_portal_rate_limit_enforced(monkeypatch):
    import uuid

    from app.core.config import settings
    from app.core.exceptions import RateLimitExceededError
    from app.core.rate_limit.limiter import check_portal_limit
    from app.core.rate_limit.memory import memory_sliding_window_reset

    monkeypatch.setattr(settings, "portal_rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "portal_rate_limit_redeem_per_minute", 2)
    memory_sliding_window_reset()
    cid = uuid.uuid4()
    await check_portal_limit(
        action="redeem",
        site_slug="hq",
        client_ip="10.0.0.1",
        customer_id=cid,
        voucher_code="CODE1",
    )
    await check_portal_limit(
        action="redeem",
        site_slug="hq",
        client_ip="10.0.0.1",
        customer_id=cid,
        voucher_code="CODE1",
    )
    with pytest.raises(RateLimitExceededError):
        await check_portal_limit(
            action="redeem",
            site_slug="hq",
            client_ip="10.0.0.1",
            customer_id=cid,
            voucher_code="CODE1",
        )


def test_reconcile_expired_grants():
    from app.modules.reconciliation.service import reconcile_expired_access_grants

    grant = SimpleNamespace(
        status=AccessGrantStatus.active.value,
        ends_at=datetime.now(UTC) - timedelta(hours=1),
    )

    class _Res:
        def scalars(self):
            return self

        def all(self):
            return [grant]

    session = MagicMock()
    session.execute = MagicMock(return_value=_Res())
    assert reconcile_expired_access_grants(session) == 1
    assert grant.status == AccessGrantStatus.expired.value


def test_reconcile_stale_pending_payments():
    from app.modules.reconciliation.service import reconcile_stale_pending_payments

    pay = SimpleNamespace(
        payment_status=PaymentStatus.pending.value,
        created_at=datetime.now(UTC) - timedelta(days=5),
        id=__import__("uuid").uuid4(),
    )

    class _Res:
        def scalars(self):
            return self

        def all(self):
            return [pay]

    session = MagicMock()
    session.add = MagicMock()
    session.execute = MagicMock(return_value=_Res())
    n = reconcile_stale_pending_payments(session, max_age_hours=72)
    assert n == 1
    assert pay.payment_status == PaymentStatus.cancelled.value
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_resilient_mikrotik_maps_not_implemented(monkeypatch):
    from app.integrations.mikrotik.errors import MikrotikIntegrationError
    from app.integrations.mikrotik.resilience import ResilientMikroTikAdapter

    monkeypatch.setattr("app.integrations.mikrotik.resilience.settings.mikrotik_max_retries", 0)

    inner = MagicMock()
    inner.test_connection = AsyncMock(side_effect=NotImplementedError("stub"))

    ad = ResilientMikroTikAdapter(inner)
    with pytest.raises(MikrotikIntegrationError) as ei:
        await ad.test_connection()
    assert ei.value.code == "not_implemented"


@pytest.mark.asyncio
async def test_process_payment_webhook_skips_duplicate_dedupe():
    import uuid
    from unittest.mock import patch

    from app.integrations.payments.callback_pipeline import process_payment_webhook
    from app.integrations.payments.types import WebhookVerificationResult

    existing = SimpleNamespace(id=uuid.uuid4(), payment_id=uuid.uuid4())
    session = MagicMock()
    r1 = MagicMock()
    r1.scalar_one_or_none = MagicMock(return_value=existing)
    session.execute = AsyncMock(return_value=r1)
    session.flush = AsyncMock()
    verification = WebhookVerificationResult(
        signature_valid=True,
        order_reference="ORD",
        provider_transaction_id="TX-DUP",
        normalized_outcome="success",
    )

    with patch("app.integrations.payments.callback_pipeline.record_audit", new=AsyncMock()):
        out = await process_payment_webhook(
            session,
            provider_name="clickpesa",
            payload={"data": {"transactionId": "TX-DUP"}},
            verification=verification,
        )

    assert out["processed"] is False
    assert out["reason"] == "duplicate_webhook"
