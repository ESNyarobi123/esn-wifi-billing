from __future__ import annotations

from celery import shared_task

from app.core.config import settings
from app.db.sync_session import sync_session_scope
from app.modules.reconciliation.service import (
    reconcile_expired_access_grants,
    reconcile_stale_pending_payments,
)


@shared_task(name="esn.reconciliation.run_once")
def run_reconciliation_pass() -> str:
    """Periodic pass: expired grants + stale pending payments (idempotent)."""
    with sync_session_scope() as session:
        g = reconcile_expired_access_grants(session)
        p = reconcile_stale_pending_payments(session, max_age_hours=settings.pending_payment_abandon_hours)
        return f"expired_grants={g}, stale_pending_cancelled={p}"
