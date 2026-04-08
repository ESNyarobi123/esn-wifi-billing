from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.responses import ok
from app.integrations.payments.callback_pipeline import process_payment_webhook
from app.integrations.payments.factory import get_payment_provider
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_PAYMENTS_READ, PERM_PAYMENTS_WRITE
from app.modules.auth.models import User
from app.modules.payments.models import Payment, PaymentEvent
from app.modules.payments.service import (
    apply_payment_success,
    create_payment_intent,
    get_payment_by_order_ref,
    refresh_payment_status_from_provider,
)

router = APIRouter()


class InitiatePaymentBody(BaseModel):
    provider: str | None = None
    amount: Decimal
    currency: str = "TZS"
    customer_id: str | None = None
    plan_id: str | None = None
    site_id: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    full_name: str | None = None


@router.get(
    "/payments/{payment_id}",
    dependencies=[Depends(require_permissions(PERM_PAYMENTS_READ))],
    summary="Get payment",
    response_description="Payment row for dashboard detail views.",
)
async def get_payment(session: DbSession, payment_id: uuid.UUID):
    pay = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if pay is None:
        raise NotFoundError("Payment not found")
    return ok(
        {
            "id": str(pay.id),
            "order_reference": pay.order_reference,
            "provider": pay.provider,
            "provider_ref": pay.provider_ref,
            "amount": str(pay.amount),
            "currency": pay.currency,
            "payment_status": pay.payment_status,
            "customer_id": str(pay.customer_id) if pay.customer_id else None,
            "plan_id": str(pay.plan_id) if pay.plan_id else None,
            "site_id": str(pay.site_id) if pay.site_id else None,
            "metadata": pay.metadata_json,
            "created_at": pay.created_at.isoformat(),
            "updated_at": pay.updated_at.isoformat(),
        },
    )


@router.get("/payments/{payment_id}/events", dependencies=[Depends(require_permissions(PERM_PAYMENTS_READ))])
async def list_payment_events(session: DbSession, payment_id: uuid.UUID, limit: int = 200):
    pay = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if pay is None:
        raise NotFoundError("Payment not found")
    rows = (
        await session.execute(
            select(PaymentEvent)
            .where(PaymentEvent.payment_id == payment_id)
            .order_by(PaymentEvent.created_at.desc())
            .limit(limit),
        )
    ).scalars().all()
    return ok(
        [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in rows
        ],
    )


@router.get("/payments", dependencies=[Depends(require_permissions(PERM_PAYMENTS_READ))])
async def list_payments(session: DbSession, limit: int = 100):
    rows = (await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(limit))).scalars().all()
    return ok(
        [
            {
                "id": str(p.id),
                "order_reference": p.order_reference,
                "provider": p.provider,
                "amount": str(p.amount),
                "currency": p.currency,
                "payment_status": p.payment_status,
            }
            for p in rows
        ],
    )


@router.post(
    "/payments/initiate",
    dependencies=[Depends(require_permissions(PERM_PAYMENTS_WRITE))],
    summary="Initiate payment (admin)",
    description="Creates a pending payment and calls the configured provider ``initiate_payment``. Use portal ``/pay`` for captive flows.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "plan_purchase": {
                            "summary": "Plan purchase",
                            "value": {
                                "amount": "5000.00",
                                "currency": "TZS",
                                "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                                "plan_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                                "email": "buyer@example.com",
                                "phone": "+255700000000",
                                "full_name": "Buyer",
                            },
                        }
                    }
                }
            }
        }
    },
)
async def initiate_payment_route(
    session: DbSession,
    body: InitiatePaymentBody,
    request: Request,
    admin: User = Depends(get_current_user),
):
    cust_id = uuid.UUID(body.customer_id) if body.customer_id else None
    plan_id = uuid.UUID(body.plan_id) if body.plan_id else None
    site_id = uuid.UUID(body.site_id) if body.site_id else None
    provider = body.provider or settings.default_payment_provider
    customer_payload = {
        "customerName": body.full_name or "",
        "customerEmail": body.email or "",
        "customerPhoneNumber": body.phone or "",
    }
    cb_base = str(request.base_url).rstrip("/")
    pay, prov = await create_payment_intent(
        session,
        provider=provider,
        amount=body.amount,
        currency=body.currency,
        customer_id=cust_id,
        plan_id=plan_id,
        site_id=site_id,
        voucher_batch_id=None,
        customer_payload=customer_payload,
        callback_url=cb_base + settings.clickpesa_webhook_path,
        metadata={"initiated_by": str(admin.id)},
    )
    await record_audit(
        session,
        user_id=admin.id,
        action="payment.initiate",
        resource_type="payment",
        resource_id=str(pay.id),
    )
    return ok({"payment": {"id": str(pay.id), "order_reference": pay.order_reference}, "provider": prov})


@router.post(
    "/payments/webhooks/clickpesa",
    summary="ClickPesa webhook",
    description="Checksum verification + idempotent processing. Replayed payloads with the same gateway txn id are acked without double activation.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "paid": {
                            "summary": "Payment received",
                            "value": {
                                "event": "PAYMENT RECEIVED",
                                "data": {
                                    "orderReference": "ESNA1B2C3D4",
                                    "status": "SUCCESS",
                                    "transactionId": "TX-1",
                                },
                                "checksum": "…",
                            },
                        }
                    }
                }
            }
        }
    },
)
async def clickpesa_webhook(session: DbSession, request: Request, payload: dict[str, Any]):
    prov = get_payment_provider("clickpesa")
    headers = {k: v for k, v in request.headers.items()}
    verification = await prov.verify_webhook(payload, headers)
    out = await process_payment_webhook(
        session,
        provider_name="clickpesa",
        payload=payload,
        verification=verification,
    )
    return ok(out, message="Acknowledged")


class MockCompleteBody(BaseModel):
    order_reference: str


@router.post("/payments/mock/complete")
async def mock_complete(session: DbSession, body: MockCompleteBody):
    pay = await get_payment_by_order_ref(session, body.order_reference)
    if pay is None:
        raise NotFoundError("Payment not found")
    if pay.provider != "mock":
        raise ValidationAppError("Not a mock payment")
    activation = await apply_payment_success(session, pay, provider_payload={"event": "MOCK_SUCCESS"})
    await record_audit(
        session,
        user_id=None,
        action="payment.mock_complete",
        resource_type="payment",
        resource_id=str(pay.id),
        details=activation,
    )
    return ok({"activation": activation}, message="Mock payment completed")


@router.post("/payments/{payment_id}/mark-success", dependencies=[Depends(require_permissions(PERM_PAYMENTS_WRITE))])
async def mark_success_override(session: DbSession, payment_id: uuid.UUID, admin: User = Depends(get_current_user)):
    pay = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if pay is None:
        raise NotFoundError("Payment not found")
    activation = await apply_payment_success(session, pay, provider_payload={"override": True})
    await record_audit(
        session,
        user_id=admin.id,
        action="payment.override_success",
        resource_type="payment",
        resource_id=str(payment_id),
        details=activation,
    )
    return ok({"activation": activation}, message="Payment marked success")


@router.post("/payments/{payment_id}/refresh-status", dependencies=[Depends(require_permissions(PERM_PAYMENTS_WRITE))])
async def refresh_payment_status(session: DbSession, payment_id: uuid.UUID, admin: User = Depends(get_current_user)):
    pay = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if pay is None:
        raise NotFoundError("Payment not found")
    result = await refresh_payment_status_from_provider(session, pay)
    await record_audit(
        session,
        user_id=admin.id,
        action="payment.refresh_status",
        resource_type="payment",
        resource_id=str(payment_id),
        details={
            "payment_status": result["payment_status"],
            "gateway_status": result["gateway_status"],
            "normalized_outcome": result["normalized_outcome"],
        },
    )
    return ok(result, message="Provider status refreshed")
