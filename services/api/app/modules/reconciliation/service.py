"""Idempotent maintenance — safe to rerun; conservative state transitions only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import AccessGrantStatus, PaymentStatus
from app.modules.payments.models import Payment, PaymentEvent
from app.modules.subscriptions.models import CustomerAccessGrant


def reconcile_expired_access_grants(session: Session) -> int:
    """Mark ``active`` grants past ``ends_at`` as ``expired``."""
    now = datetime.now(UTC)
    q = select(CustomerAccessGrant).where(
        CustomerAccessGrant.status == AccessGrantStatus.active.value,
        CustomerAccessGrant.ends_at.isnot(None),
        CustomerAccessGrant.ends_at < now,
    )
    rows = list(session.execute(q).scalars().all())
    for g in rows:
        g.status = AccessGrantStatus.expired.value
    return len(rows)


def reconcile_stale_pending_payments(session: Session, *, max_age_hours: int) -> int:
    """Cancel long-pending payments (webhook never arrived); records a ``stale_cancelled`` event."""
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    q = select(Payment).where(
        Payment.payment_status == PaymentStatus.pending.value,
        Payment.created_at < cutoff,
    )
    rows = list(session.execute(q).scalars().all())
    n = 0
    for p in rows:
        p.payment_status = PaymentStatus.cancelled.value
        session.add(
            PaymentEvent(
                payment_id=p.id,
                event_type="stale_cancelled",
                payload={"cutoff_utc": cutoff.isoformat(), "max_age_hours": max_age_hours},
            ),
        )
        n += 1
    return n
