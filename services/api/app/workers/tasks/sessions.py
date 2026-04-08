from __future__ import annotations

from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

from app.db.enums import SessionStatus, VoucherStatus
from app.db.sync_session import sync_session_scope
from app.modules.sessions.models import HotspotSession
from app.modules.vouchers.models import Voucher


@shared_task(name="esn.sessions.expire_stale")
def expire_stale_sessions() -> str:
    now = datetime.now(UTC)
    with sync_session_scope() as session:
        q = select(HotspotSession).where(
            HotspotSession.status == SessionStatus.active.value,
            HotspotSession.expires_at.isnot(None),
            HotspotSession.expires_at < now,
        )
        rows = list(session.execute(q).scalars().all())
        for s in rows:
            s.status = SessionStatus.expired.value
        return f"expired {len(rows)} sessions"


@shared_task(name="esn.vouchers.mark_expired")
def mark_expired_vouchers() -> str:
    now = datetime.now(UTC)
    with sync_session_scope() as session:
        q = select(Voucher).where(
            Voucher.status.in_([VoucherStatus.unused.value, VoucherStatus.active.value]),
            Voucher.expires_at.isnot(None),
            Voucher.expires_at < now,
        )
        rows = list(session.execute(q).scalars().all())
        for v in rows:
            v.status = VoucherStatus.expired.value
        return f"expired {len(rows)} vouchers"
