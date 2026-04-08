from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment


async def notify_customer_payment(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    payment: Payment,
    success: bool,
    extra: dict[str, Any] | None = None,
) -> Notification:
    if success:
        title = "Payment received"
        body = f"Order {payment.order_reference} succeeded — {payment.amount} {payment.currency}"
        ntype = "payment_success"
    else:
        title = "Payment failed"
        body = f"Order {payment.order_reference} did not complete."
        ntype = "payment_failed"
    n = Notification(
        customer_id=customer_id,
        type=ntype,
        title=title,
        body=body,
        status="active",
        data={"payment_id": str(payment.id), "order_reference": payment.order_reference, **(extra or {})},
    )
    session.add(n)
    await session.flush()
    return n


async def notify_customer_voucher_redeemed(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    plan_name: str,
    voucher_code: str,
    ends_at: datetime | None,
) -> None:
    n = Notification(
        customer_id=customer_id,
        type="voucher_redeemed",
        title="Voucher activated",
        body=f"Plan «{plan_name}» is now active (code {voucher_code}).",
        status="active",
        data={
            "voucher_code": voucher_code,
            "ends_at": ends_at.isoformat() if ends_at else None,
        },
    )
    session.add(n)
    await session.flush()


async def notify_router_offline(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    router_name: str,
    router_id: uuid.UUID,
) -> Notification:
    n = Notification(
        user_id=user_id,
        type="router_offline",
        title="Router offline",
        body=f"NAS «{router_name}» appears offline.",
        status="active",
        data={"router_id": str(router_id)},
    )
    session.add(n)
    await session.flush()
    return n
