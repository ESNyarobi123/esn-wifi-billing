from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.enums import AccessGrantSource, AccessGrantStatus, PlanType
from app.modules.customers.models import Customer
from app.modules.payments.models import Payment
from app.modules.plans.models import Plan, PlanRouterAvailability
from app.modules.routers.models import Router, Site
from app.modules.subscriptions.models import CustomerAccessGrant


def compute_grant_entitlement(*, grant: CustomerAccessGrant, plan: Plan | None, now: datetime | None = None) -> dict[str, Any]:
    """Derive user-facing entitlement state (calendar + plan rules, no DB)."""
    ts = now or datetime.now(UTC)
    raw_status = grant.status
    if raw_status in (AccessGrantStatus.revoked.value, AccessGrantStatus.cancelled.value, AccessGrantStatus.consumed.value):
        return {
            "status": raw_status,
            "is_usable": False,
            "starts_at": grant.starts_at.isoformat(),
            "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
            "reason": "not_entitled",
        }
    if grant.starts_at > ts:
        return {
            "status": AccessGrantStatus.pending.value,
            "is_usable": False,
            "starts_at": grant.starts_at.isoformat(),
            "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
            "reason": "not_started",
        }
    if grant.ends_at and grant.ends_at <= ts:
        return {
            "status": AccessGrantStatus.expired.value,
            "is_usable": False,
            "starts_at": grant.starts_at.isoformat(),
            "ends_at": grant.ends_at.isoformat(),
            "reason": "expired",
        }
    if raw_status == AccessGrantStatus.pending.value:
        return {
            "status": AccessGrantStatus.pending.value,
            "is_usable": False,
            "starts_at": grant.starts_at.isoformat(),
            "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
            "reason": "pending",
        }
    is_active = raw_status == AccessGrantStatus.active.value
    return {
        "status": AccessGrantStatus.active.value if is_active else raw_status,
        "is_usable": bool(is_active),
        "starts_at": grant.starts_at.isoformat(),
        "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
        "plan_type": plan.plan_type if plan else None,
        "reason": "ok" if is_active else "inactive",
    }


async def is_plan_offered_at_site(session: AsyncSession, *, site_id: uuid.UUID, plan_id: uuid.UUID) -> bool:
    """Align with portal plan listing: plan must be active and allowed on site's NAS (or global fallback)."""
    plan = (await session.execute(select(Plan).where(Plan.id == plan_id, Plan.is_active.is_(True)))).scalar_one_or_none()
    if plan is None:
        return False
    router_ids = (
        await session.execute(select(Router.id).where(Router.site_id == site_id, Router.status != "deleted"))
    ).scalars().all()
    if not router_ids:
        return True
    rows = (
        await session.execute(
            select(PlanRouterAvailability.plan_id).where(PlanRouterAvailability.router_id.in_(router_ids)),
        )
    ).scalars().all()
    unique = {pid for pid in rows}
    if not unique:
        return True
    return plan_id in unique


async def _create_access_grant(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    plan_id: uuid.UUID,
    site_id: uuid.UUID | None,
    source: str,
    voucher_id: uuid.UUID | None,
    payment_id: uuid.UUID | None,
    status: str | None = None,
) -> CustomerAccessGrant:
    plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan not found")
    now = datetime.now(UTC)
    ends: datetime | None = None
    if plan.plan_type in (PlanType.time.value, PlanType.data.value) and plan.duration_seconds:
        ends = now + timedelta(seconds=int(plan.duration_seconds))
    if plan.plan_type == PlanType.unlimited.value:
        ends = None
    grant = CustomerAccessGrant(
        customer_id=customer_id,
        site_id=site_id,
        plan_id=plan_id,
        voucher_id=voucher_id,
        payment_id=payment_id,
        source=source,
        status=status or AccessGrantStatus.active.value,
        starts_at=now,
        ends_at=ends,
    )
    session.add(grant)
    await session.flush()
    return grant


async def grant_access_from_voucher(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    plan_id: uuid.UUID,
    voucher_id: uuid.UUID,
    site_id: uuid.UUID | None = None,
) -> CustomerAccessGrant:
    return await _create_access_grant(
        session,
        customer_id=customer_id,
        plan_id=plan_id,
        site_id=site_id,
        source=AccessGrantSource.voucher.value,
        voucher_id=voucher_id,
        payment_id=None,
    )


async def grant_access_from_payment(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    plan_id: uuid.UUID,
    payment_id: uuid.UUID,
    site_id: uuid.UUID | None = None,
) -> CustomerAccessGrant:
    return await _create_access_grant(
        session,
        customer_id=customer_id,
        plan_id=plan_id,
        site_id=site_id,
        source=AccessGrantSource.payment.value,
        voucher_id=None,
        payment_id=payment_id,
    )


async def get_grant_by_payment_id(session: AsyncSession, payment_id: uuid.UUID) -> CustomerAccessGrant | None:
    return (
        await session.execute(select(CustomerAccessGrant).where(CustomerAccessGrant.payment_id == payment_id))
    ).scalar_one_or_none()


async def get_grant_by_voucher_id(session: AsyncSession, voucher_id: uuid.UUID) -> CustomerAccessGrant | None:
    return (
        await session.execute(select(CustomerAccessGrant).where(CustomerAccessGrant.voucher_id == voucher_id))
    ).scalar_one_or_none()


async def ensure_payment_activation_grant(session: AsyncSession, payment: Payment) -> CustomerAccessGrant | None:
    """If payment is successful and has customer+plan, ensure exactly one grant exists (idempotent repair)."""
    if payment.payment_status != "success" or not payment.plan_id or not payment.customer_id:
        return None
    existing = await get_grant_by_payment_id(session, payment.id)
    if existing:
        return existing
    return await grant_access_from_payment(
        session,
        customer_id=payment.customer_id,
        plan_id=payment.plan_id,
        payment_id=payment.id,
        site_id=payment.site_id,
    )


async def serialize_access_grants_for_customer(
    session: AsyncSession,
    customer_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    grants = (
        await session.execute(
            select(CustomerAccessGrant)
            .where(CustomerAccessGrant.customer_id == customer_id)
            .order_by(CustomerAccessGrant.starts_at.desc())
            .limit(limit),
        )
    ).scalars().all()
    out: list[dict[str, Any]] = []
    for g in grants:
        plan = (await session.execute(select(Plan).where(Plan.id == g.plan_id))).scalar_one_or_none()
        ent = compute_grant_entitlement(grant=g, plan=plan)
        out.append(
            {
                "id": str(g.id),
                "plan_id": str(g.plan_id),
                "plan_name": plan.name if plan else None,
                "site_id": str(g.site_id) if g.site_id else None,
                "source": g.source,
                "status": g.status,
                "starts_at": g.starts_at.isoformat(),
                "ends_at": g.ends_at.isoformat() if g.ends_at else None,
                "voucher_id": str(g.voucher_id) if g.voucher_id else None,
                "payment_id": str(g.payment_id) if g.payment_id else None,
                "entitlement": ent,
            },
        )
    return out


async def build_portal_access_status(
    session: AsyncSession,
    *,
    site_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> dict[str, Any]:
    cust = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if cust is None:
        raise NotFoundError("Customer not found")
    if cust.site_id and cust.site_id != site_id:
        # Customer primary site mismatch — still allow read if they belong elsewhere (soft check)
        pass
    site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    grants = (
        await session.execute(
            select(CustomerAccessGrant)
            .where(CustomerAccessGrant.customer_id == customer_id)
            .order_by(CustomerAccessGrant.starts_at.desc()),
        )
    ).scalars().all()
    now = datetime.now(UTC)
    usable: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for g in grants:
        if g.site_id is not None and g.site_id != site_id:
            continue
        plan = (await session.execute(select(Plan).where(Plan.id == g.plan_id))).scalar_one_or_none()
        ent = compute_grant_entitlement(grant=g, plan=plan, now=now)
        row = {
            "grant_id": str(g.id),
            "plan_id": str(g.plan_id),
            "plan_name": plan.name if plan else None,
            "source": g.source,
            "entitlement": ent,
        }
        if ent.get("is_usable"):
            usable.append(row)
            if best is None:
                best = row
    return {
        "site": {"id": str(site.id), "name": site.name, "slug": site.slug} if site else None,
        "customer_id": str(customer_id),
        "has_usable_access": len(usable) > 0,
        "primary_access": best,
        "usable_grants": usable,
    }
