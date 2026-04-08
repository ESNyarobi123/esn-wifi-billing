from __future__ import annotations

import secrets
import uuid
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.integrations.payments.errors import normalize_provider_http_error
from app.db.enums import PaymentStatus, VoucherStatus
from app.integrations.payments.factory import get_payment_provider
from app.modules.payments.models import Payment, PaymentEvent
from app.modules.plans.models import Plan
from app.modules.routers.hotspot_authorization_service import (
    authorize_best_portal_access,
    build_hotspot_device_context,
)
from app.modules.routers.models import Site
from app.modules.subscriptions import service as subs_service
from app.modules.subscriptions.models import CustomerAccessGrant
from app.modules.vouchers.models import Voucher, VoucherBatch


def _order_ref() -> str:
    return f"ESN{secrets.token_hex(8).upper()}"


async def create_payment_intent(
    session: AsyncSession,
    *,
    provider: str,
    amount: Decimal,
    currency: str,
    customer_id: uuid.UUID | None,
    plan_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
    voucher_batch_id: uuid.UUID | None,
    customer_payload: dict[str, Any],
    callback_url: str | None,
    metadata: dict[str, Any] | None,
) -> tuple[Payment, dict[str, Any]]:
    plan: Plan | None = None
    if plan_id:
        plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Plan not found")
        if amount != Decimal(str(plan.price_amount)):
            raise ValidationAppError("Amount must match plan price")

    order_reference = _order_ref()
    pay = Payment(
        provider=provider,
        order_reference=order_reference,
        amount=float(amount),
        currency=currency,
        payment_status=PaymentStatus.pending.value,
        customer_id=customer_id,
        plan_id=plan_id,
        voucher_batch_id=voucher_batch_id,
        site_id=site_id,
        metadata_json=metadata,
    )
    session.add(pay)
    await session.flush()

    prov = get_payment_provider(provider)
    try:
        prov_body = await prov.initiate_payment(
            order_reference=order_reference,
            amount=str(amount),
            currency=currency,
            customer=customer_payload,
            callback_url=callback_url,
            metadata={"payment_id": str(pay.id), **(metadata or {})},
        )
    except httpx.HTTPError as e:
        raise normalize_provider_http_error(e, provider=provider) from e
    except RuntimeError as e:
        raise normalize_provider_http_error(e, provider=provider) from e
    provider_ref = (
        prov_body.get("payment_reference")
        or prov_body.get("external_reference")
        or prov_body.get("provider_ref")
        or pay.provider_ref
    )
    if provider_ref:
        pay.provider_ref = str(provider_ref)
    event = PaymentEvent(payment_id=pay.id, event_type="initiated", payload=prov_body)
    session.add(event)
    await session.flush()
    return pay, prov_body


async def _sync_voucher_batch_after_payment(session: AsyncSession, payment: Payment) -> None:
    if not payment.voucher_batch_id:
        return
    batch = (await session.execute(select(VoucherBatch).where(VoucherBatch.id == payment.voucher_batch_id))).scalar_one_or_none()
    if batch is None:
        return
    vos = (
        await session.execute(
            select(Voucher).where(Voucher.batch_id == batch.id, Voucher.status == VoucherStatus.unused.value),
        )
    ).scalars().all()
    for v in vos:
        v.status = VoucherStatus.active.value
        if payment.customer_id:
            v.assigned_customer_id = payment.customer_id


async def activate_access_after_successful_payment(
    session: AsyncSession,
    payment: Payment,
    *,
    provider_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Canonical success path: mark payment succeeded, record one ``success`` event, create entitlement,
    activate batch vouchers, notify customer. Idempotent for webhook/mock-complete retries.
    """
    if payment.payment_status == PaymentStatus.success.value:
        grant = await subs_service.ensure_payment_activation_grant(session, payment)
        await _sync_voucher_batch_after_payment(session, payment)
        return {
            "idempotent_replay": True,
            "payment_id": str(payment.id),
            "grant_id": str(grant.id) if grant else None,
            "activated": grant is not None,
        }

    payment.payment_status = PaymentStatus.success.value
    session.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="success",
            payload=provider_payload,
        ),
    )

    grant: CustomerAccessGrant | None = None
    if payment.plan_id and payment.customer_id:
        grant = await subs_service.grant_access_from_payment(
            session,
            customer_id=payment.customer_id,
            plan_id=payment.plan_id,
            payment_id=payment.id,
            site_id=payment.site_id,
        )

    await _sync_voucher_batch_after_payment(session, payment)

    if payment.customer_id:
        from app.modules.notifications.service import notify_customer_payment

        await notify_customer_payment(
            session,
            customer_id=payment.customer_id,
            payment=payment,
            success=True,
            extra={"provider": payment.provider},
        )

    authorization: dict[str, Any] | None = None
    hotspot_context = None
    metadata_json = getattr(payment, "metadata_json", None)
    if isinstance(metadata_json, dict):
        hotspot_context = metadata_json.get("hotspot_context")
    if payment.customer_id and payment.site_id and hotspot_context:
        site = (await session.execute(select(Site).where(Site.id == payment.site_id))).scalar_one_or_none()
        context = build_hotspot_device_context(hotspot_context if isinstance(hotspot_context, dict) else None)
        if site and context:
            authorization = await authorize_best_portal_access(
                session,
                site=site,
                customer_id=payment.customer_id,
                context=context,
            )
            if authorization is not None:
                session.add(
                    PaymentEvent(
                        payment_id=payment.id,
                        event_type="router_authorization",
                        payload=authorization,
                    ),
                )

    return {
        "idempotent_replay": False,
        "payment_id": str(payment.id),
        "grant_id": str(grant.id) if grant else None,
        "activated": grant is not None,
        "authorization": authorization,
    }


async def apply_payment_success(
    session: AsyncSession,
    payment: Payment,
    *,
    provider_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backward-compatible alias for :func:`activate_access_after_successful_payment`."""
    return await activate_access_after_successful_payment(session, payment, provider_payload=provider_payload)


async def apply_payment_failed(session: AsyncSession, payment: Payment, *, reason: dict | None) -> None:
    if payment.payment_status == PaymentStatus.failed.value:
        return
    if payment.payment_status == PaymentStatus.success.value:
        return
    payment.payment_status = PaymentStatus.failed.value
    session.add(PaymentEvent(payment_id=payment.id, event_type="failed", payload=reason))
    if payment.customer_id:
        from app.modules.notifications.service import notify_customer_payment

        await notify_customer_payment(
            session,
            customer_id=payment.customer_id,
            payment=payment,
            success=False,
            extra={"reason": reason},
        )


async def get_payment_by_order_ref(session: AsyncSession, order_reference: str) -> Payment | None:
    stmt = select(Payment).where(Payment.order_reference == order_reference)
    return (await session.execute(stmt)).scalar_one_or_none()


async def refresh_payment_status_from_provider(session: AsyncSession, payment: Payment) -> dict[str, Any]:
    provider = get_payment_provider(payment.provider)
    try:
        status_data = await provider.query_payment_status(order_reference=payment.order_reference)
    except httpx.HTTPError as e:
        raise normalize_provider_http_error(e, provider=payment.provider) from e
    except RuntimeError as e:
        raise normalize_provider_http_error(e, provider=payment.provider) from e

    gateway_status = str(status_data.get("gateway_status") or "").upper() or None
    normalized = str(status_data.get("normalized_outcome") or "").lower() or "unknown"
    provider_ref = status_data.get("payment_reference") or status_data.get("provider_transaction_id")
    if provider_ref:
        payment.provider_ref = str(provider_ref)

    session.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="provider_status_sync",
            payload=status_data,
        ),
    )

    activation: dict[str, Any] | None = None
    if normalized == "success":
        activation = await apply_payment_success(session, payment, provider_payload=status_data)
    elif normalized == "failure":
        await apply_payment_failed(session, payment, reason=status_data)

    await session.flush()
    return {
        "payment_id": str(payment.id),
        "provider": payment.provider,
        "order_reference": payment.order_reference,
        "gateway_status": gateway_status,
        "normalized_outcome": normalized,
        "provider_ref": payment.provider_ref,
        "payment_status": payment.payment_status,
        "activation": activation,
        "provider_data": status_data,
    }
