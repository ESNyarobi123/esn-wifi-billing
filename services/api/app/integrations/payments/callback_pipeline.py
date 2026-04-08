"""Map verified provider webhooks to idempotent business activation (separate from provider adapters)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.integrations.payments.dedupe import compute_webhook_dedupe_key
from app.integrations.payments.types import WebhookVerificationResult, summarize_payload_for_logs
from app.modules.access_control.audit_service import record_audit
from app.modules.payments.models import Payment, PaymentCallback
from app.modules.payments.service import apply_payment_failed, apply_payment_success, get_payment_by_order_ref


async def process_payment_webhook(
    session: AsyncSession,
    *,
    provider_name: str,
    payload: dict[str, Any],
    verification: WebhookVerificationResult,
    record_raw_callback: bool = True,
) -> dict[str, Any]:
    """
    Persist callback (with dedupe), apply success/failure if applicable, audit.
    Duplicate ``dedupe_key`` for the same provider → no second activation (replay safe).
    """
    dedupe_key = compute_webhook_dedupe_key(provider=provider_name, payload=payload, result=verification)

    existing = (
        await session.execute(
            select(PaymentCallback).where(
                PaymentCallback.provider == provider_name,
                PaymentCallback.dedupe_key == dedupe_key,
            ),
        )
    ).scalar_one_or_none()
    if existing is not None:
        rid = str(existing.payment_id) if existing.payment_id else None
        await record_audit(
            session,
            user_id=None,
            action="payment.webhook_duplicate_skipped",
            resource_type="payment",
            resource_id=rid,
            details={
                "provider": provider_name,
                "dedupe_key": dedupe_key,
                "summary": summarize_payload_for_logs(payload),
            },
        )
        await session.flush()
        return {
            "processed": False,
            "reason": "duplicate_webhook",
            "payment_id": rid,
            "dedupe_key": dedupe_key,
        }

    order_ref = verification.order_reference
    pay = await get_payment_by_order_ref(session, order_ref) if order_ref else None

    cb = PaymentCallback(
        payment_id=pay.id if pay else None,
        provider=provider_name,
        event_type=verification.provider_event_type,
        raw_payload=payload,
        checksum_valid=verification.signature_valid,
        dedupe_key=dedupe_key,
    )
    try:
        async with session.begin_nested():
            session.add(cb)
            await session.flush()
    except IntegrityError:
        await record_audit(
            session,
            user_id=None,
            action="payment.webhook_duplicate_skipped",
            resource_type="payment",
            resource_id=str(pay.id) if pay else None,
            details={"provider": provider_name, "dedupe_key": dedupe_key, "reason": "concurrent_insert"},
        )
        await session.flush()
        return {"processed": False, "reason": "duplicate_webhook", "dedupe_key": dedupe_key}

    if pay is None:
        await record_audit(
            session,
            user_id=None,
            action="payment.webhook_orphan_callback",
            resource_type="payment",
            resource_id=None,
            details={
                "provider": provider_name,
                "dedupe_key": dedupe_key,
                "summary": summarize_payload_for_logs(payload),
            },
        )
        await session.flush()
        return {"processed": False, "reason": "order_not_found", "dedupe_key": dedupe_key}

    if provider_name == "clickpesa" and not verification.signature_valid and settings.clickpesa_checksum_key:
        raise ValidationAppError("Invalid webhook signature")

    outcome_action = "noop"
    if verification.normalized_outcome == "success":
        await apply_payment_success(session, pay, provider_payload=payload)
        outcome_action = "success"
    elif verification.normalized_outcome == "failure":
        await apply_payment_failed(session, pay, reason=payload)
        outcome_action = "failed"

    await record_audit(
        session,
        user_id=None,
        action="payment.webhook_processed",
        resource_type="payment",
        resource_id=str(pay.id),
        details={
            "provider": provider_name,
            "outcome": outcome_action,
            "normalized": verification.normalized_outcome,
            "signature_valid": verification.signature_valid,
            "dedupe_key": dedupe_key,
            "summary": summarize_payload_for_logs(payload),
        },
    )
    await session.flush()
    return {
        "processed": True,
        "payment_id": str(pay.id),
        "outcome": outcome_action,
        "dedupe_key": dedupe_key,
    }
