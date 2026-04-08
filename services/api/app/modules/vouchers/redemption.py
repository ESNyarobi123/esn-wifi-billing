"""End-to-end voucher redemption: lock row, validate, grant access, audit, notify."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.db.enums import VoucherStatus
from app.modules.access_control.audit_service import record_audit
from app.modules.plans.models import Plan
from app.modules.routers.hotspot_authorization_service import (
    authorize_grant_for_device,
    build_hotspot_device_context,
    resolve_site_router,
)
from app.modules.routers.models import Site
from app.modules.subscriptions import service as subs_service
from app.modules.subscriptions.models import CustomerAccessGrant
from app.modules.vouchers.models import Voucher


def _normalize_code(code: str) -> str:
    return code.strip().upper()


async def redeem_voucher(
    session: AsyncSession,
    *,
    site_id: uuid.UUID | None,
    code: str,
    pin: str | None,
    customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    channel: str,
    enforce_site_plan: bool = True,
    ip_address: str | None = None,
    user_agent: str | None = None,
    hotspot_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Redeem a voucher for a customer at a site.

    - Uses ``SELECT ... FOR UPDATE`` to reduce double-redemption races.
    - Idempotent when the same customer repeats a successful redemption (same grant).
    - Standard portal contract: ``success``, ``activated_plan``, ``access``, ``voucher``.
    """
    normalized = _normalize_code(code)
    v = (
        await session.execute(select(Voucher).where(Voucher.code == normalized).with_for_update())
    ).scalar_one_or_none()
    if v is None:
        raise NotFoundError("Voucher code not found")

    if v.status == VoucherStatus.disabled.value:
        raise ValidationAppError("This voucher has been disabled")

    if v.expires_at and v.expires_at < datetime.now(UTC):
        v.status = VoucherStatus.expired.value
        await session.flush()
        raise ValidationAppError("This voucher has expired")

    if v.pin and pin != v.pin:
        raise ValidationAppError("Invalid PIN")

    plan = (await session.execute(select(Plan).where(Plan.id == v.plan_id))).scalar_one_or_none()
    if plan is None or not plan.is_active:
        raise ValidationAppError("This voucher's plan is not available")

    if enforce_site_plan:
        if site_id is None:
            raise ValidationAppError("site context is required for this redemption")
        if not await subs_service.is_plan_offered_at_site(session, site_id=site_id, plan_id=v.plan_id):
            raise ValidationAppError("This plan is not available at this hotspot")

    if v.status == VoucherStatus.used.value:
        grant = await subs_service.get_grant_by_voucher_id(session, v.id)
        if grant is None:
            raise ValidationAppError("Voucher already used")
        if grant.customer_id != customer_id:
            raise ConflictError("Voucher was redeemed by another customer")
        plan_g = (await session.execute(select(Plan).where(Plan.id == grant.plan_id))).scalar_one_or_none()
        ent = subs_service.compute_grant_entitlement(grant=grant, plan=plan_g)
        auth = await _build_authorization_payload(
            session=session,
            site_id=site_id,
            plan=plan_g or plan,
            grant=grant,
            hotspot_context=hotspot_context,
        )
        return _success_payload(
            voucher=v,
            plan=plan_g or plan,
            grant=grant,
            entitlement=ent,
            idempotent=True,
            authorization=auth,
        )

    if v.status not in (VoucherStatus.unused.value, VoucherStatus.active.value):
        raise ValidationAppError("Voucher not redeemable")

    grant: CustomerAccessGrant | None = None
    idempotent_insert = False
    try:
        async with session.begin_nested():
            grant = await subs_service.grant_access_from_voucher(
                session,
                customer_id=customer_id,
                plan_id=v.plan_id,
                voucher_id=v.id,
                site_id=site_id,
            )
    except IntegrityError:
        grant = await subs_service.get_grant_by_voucher_id(session, v.id)
        if grant is None:
            raise ConflictError("Could not complete redemption") from None
        idempotent_insert = True
        if grant.customer_id != customer_id:
            raise ConflictError("Voucher was redeemed by another customer")

    if v.status != VoucherStatus.used.value:
        v.status = VoucherStatus.used.value
        v.assigned_customer_id = customer_id
        await session.flush()

    assert grant is not None
    entitlement = subs_service.compute_grant_entitlement(grant=grant, plan=plan)

    if not idempotent_insert:
        await record_audit(
            session,
            user_id=actor_user_id,
            action="voucher.redeemed",
            resource_type="voucher",
            resource_id=str(v.id),
            details={
                "channel": channel,
                "customer_id": str(customer_id),
                "grant_id": str(grant.id),
                "site_id": str(site_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    from app.modules.notifications.service import notify_customer_voucher_redeemed

    if not idempotent_insert:
        await notify_customer_voucher_redeemed(
            session,
            customer_id=customer_id,
            plan_name=plan.name,
            voucher_code=v.code,
            ends_at=grant.ends_at,
        )

    auth = await _build_authorization_payload(
        session=session,
        site_id=site_id,
        plan=plan,
        grant=grant,
        hotspot_context=hotspot_context,
    )

    return _success_payload(
        voucher=v,
        plan=plan,
        grant=grant,
        entitlement=entitlement,
        idempotent=idempotent_insert,
        authorization=auth,
    )


def _success_payload(
    *,
    voucher: Voucher,
    plan: Plan,
    grant: CustomerAccessGrant,
    entitlement: dict[str, Any],
    idempotent: bool,
    authorization: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "success": True,
        "idempotent": idempotent,
        "voucher": {
            "id": str(voucher.id),
            "code": voucher.code,
            "status": voucher.status,
        },
        "activated_plan": {
            "id": str(plan.id),
            "name": plan.name,
            "plan_type": plan.plan_type,
        },
        "access": {
            "grant_id": str(grant.id),
            "starts_at": grant.starts_at.isoformat(),
            "ends_at": grant.ends_at.isoformat() if grant.ends_at else None,
            "site_id": str(grant.site_id) if grant.site_id else None,
            "entitlement": entitlement,
        },
        "authorization": authorization,
    }


async def _build_authorization_payload(
    *,
    session: AsyncSession,
    site_id: uuid.UUID | None,
    plan: Plan,
    grant: CustomerAccessGrant,
    hotspot_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    context = build_hotspot_device_context(hotspot_context)
    if site_id is None or context is None:
        return None
    site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    if site is None:
        return None
    router = await resolve_site_router(session, site=site, context=context)
    if router is None:
        return {
            "available": False,
            "reason": "router_context_missing",
            "nas": {"ok": True, "notes": "router_not_resolved"},
        }
    return await authorize_grant_for_device(
        session,
        site=site,
        router=router,
        grant=grant,
        plan=plan,
        context=context,
    )
