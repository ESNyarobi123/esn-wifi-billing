from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import DbSession, get_client_ip
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.rate_limit.deps import (
    portal_rate_limit_access_status,
    portal_rate_limit_pay_body,
    portal_rate_limit_redeem_body,
    portal_rate_limit_session_body,
)
from app.core.responses import ok
from app.db.enums import RecordStatus, SessionStatus
from app.modules.payments.service import create_payment_intent
from app.modules.plans.models import Plan, PlanRouterAvailability
from app.modules.portal.models import PortalBranding
from app.modules.routers.hotspot_authorization_service import (
    authorize_best_portal_access,
    build_hotspot_device_context,
    resolve_portal_customer_id,
)
from app.modules.routers.models import Router, Site
from app.modules.settings.models import SystemSetting
from app.modules.sessions.models import HotspotSession
from app.modules.subscriptions import service as subs_service
from app.modules.vouchers.redemption import redeem_voucher
from app.schemas.portal import PortalPayBody, PortalRedeemBody, PortalSessionQuery

router = APIRouter()



@router.get("/portal/{site_slug}/branding")
async def portal_branding(session: DbSession, site_slug: str):
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    branding = (
        await session.execute(select(PortalBranding).where(PortalBranding.site_id == site.id))
    ).scalar_one_or_none()
    data = {
        "site": {"id": str(site.id), "name": site.name, "slug": site.slug},
        "branding": None,
    }
    if branding:
        data["branding"] = {
            "logo_url": branding.logo_url,
            "primary_color": branding.primary_color,
            "welcome_message": branding.welcome_message,
            "support_phone": branding.support_phone,
            "extra": branding.extra,
        }
    return ok(data)


@router.get("/portal/{site_slug}/settings")
async def portal_public_settings(session: DbSession, site_slug: str):
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    keys = settings.portal_public_setting_keys_list
    settings_out: dict = {}
    if keys:
        rows = (await session.execute(select(SystemSetting).where(SystemSetting.key.in_(keys)))).scalars().all()
        settings_out = {r.key: r.value for r in rows}
    return ok(
        {
            "site": {"id": str(site.id), "name": site.name, "slug": site.slug, "timezone": site.timezone},
            "settings": settings_out,
        },
    )


@router.get("/portal/{site_slug}/status")
async def portal_public_status(session: DbSession, site_slug: str):
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(Router).where(
                    Router.site_id == site.id,
                    Router.status != "deleted",
                ),
            )
        ).scalar_one(),
    )
    online = int(
        (
            await session.execute(
                select(func.count()).select_from(Router).where(
                    Router.site_id == site.id,
                    Router.status != "deleted",
                    Router.is_online.is_(True),
                ),
            )
        ).scalar_one(),
    )
    return ok(
        {
            "site": {"name": site.name, "slug": site.slug, "timezone": site.timezone},
            "routers": {"total": total, "online": online},
        },
    )


@router.get("/portal/{site_slug}/plans")
async def portal_plans(session: DbSession, site_slug: str):
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    router_ids = (
        await session.execute(select(Router.id).where(Router.site_id == site.id))
    ).scalars().all()
    if not router_ids:
        return ok([])
    plan_ids = (
        await session.execute(
            select(PlanRouterAvailability.plan_id).where(PlanRouterAvailability.router_id.in_(router_ids)),
        )
    ).scalars().all()
    unique_plan_ids = list({pid for pid in plan_ids})
    if not unique_plan_ids:
        plans = (
            await session.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.name))
        ).scalars().all()
    else:
        plans = (
            await session.execute(
                select(Plan).where(Plan.id.in_(unique_plan_ids), Plan.is_active.is_(True)).order_by(Plan.name),
            )
        ).scalars().all()
    return ok(
        [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "plan_type": p.plan_type,
                "price_amount": str(p.price_amount),
                "currency": p.currency,
            }
            for p in plans
        ],
    )


@router.post(
    "/portal/{site_slug}/pay",
    summary="Initiate portal payment",
    description="Distributed Redis sliding-window limit (set ``PORTAL_RATE_LIMIT_BACKEND=redis`` in production). Response includes stable ``payment`` plus PSP ``checkout`` payload.",
)
async def portal_initiate_payment(
    session: DbSession,
    site_slug: str,
    body: PortalPayBody = Depends(portal_rate_limit_pay_body),
):
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    context = build_hotspot_device_context(body.hotspot_context)
    resolved_customer_id, _resolved_by = await resolve_portal_customer_id(
        session,
        site_id=site.id,
        customer_id=body.customer_id,
        mac_address=context.mac_address if context else None,
    )
    customer_payload = {
        "customerName": body.full_name or "",
        "customerEmail": body.email or "",
        "customerPhoneNumber": body.phone or "",
    }
    pay, prov = await create_payment_intent(
        session,
        provider=settings.default_payment_provider,
        amount=body.amount,
        currency=body.currency,
        customer_id=resolved_customer_id,
        plan_id=body.plan_id,
        site_id=site.id,
        voucher_batch_id=None,
        customer_payload=customer_payload,
        callback_url=None,
        metadata={
            "portal_site": site.slug,
            "hotspot_context": body.hotspot_context,
        },
    )
    payment = {
        "id": str(pay.id),
        "order_reference": pay.order_reference,
        "amount": str(pay.amount),
        "currency": pay.currency,
        "status": pay.payment_status,
        "provider": pay.provider,
    }
    return ok(
        {
            "payment_id": str(pay.id),
            "order_reference": pay.order_reference,
            "payment": payment,
            "checkout": prov,
            "provider": prov,
        },
    )


@router.post(
    "/portal/{site_slug}/redeem",
    summary="Redeem voucher",

    description="Requires ``customer_id`` in JSON body. Idempotent for same customer + already-used voucher. Rate limit key: IP + site + customer + voucher fingerprint.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "redeem": {
                            "value": {
                                "code": "DEMO-VOUCHER",
                                "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                            }
                        }
                    }
                }
            }
        }
    },
)
async def portal_redeem(
    request: Request,
    session: DbSession,
    site_slug: str,
    body: PortalRedeemBody = Depends(portal_rate_limit_redeem_body),
):
    """Redeem a voucher at a portal site: validates plan availability, grants access, audit + notification.

    Response ``data`` includes ``success``, ``activated_plan``, ``access`` (grant + entitlement), and ``voucher``.
    Idempotent when the same customer repeats a successful redemption.
    """
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    context = build_hotspot_device_context(body.hotspot_context)
    resolved_customer_id, _resolved_by = await resolve_portal_customer_id(
        session,
        site_id=site.id,
        customer_id=body.customer_id,
        mac_address=context.mac_address if context else None,
    )
    if resolved_customer_id is None:
        raise ValidationAppError("Enter your customer ID or redeem from a device that is already linked to your account.")
    result = await redeem_voucher(
        session,
        site_id=site.id,
        code=body.code,
        pin=body.pin,
        customer_id=resolved_customer_id,
        actor_user_id=None,
        channel="portal",
        enforce_site_plan=True,
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        hotspot_context=body.hotspot_context,
    )
    return ok(result, message="Redeemed")


@router.get(
    "/portal/{site_slug}/access-status",
    dependencies=[Depends(portal_rate_limit_access_status)],
    summary="Customer access status",
)

async def portal_access_status(
    session: DbSession,
    site_slug: str,
    customer_id: uuid.UUID | None = None,
    mac_address: str | None = None,
    router_id: uuid.UUID | None = None,
    hotspot_login_url: str | None = None,
    hotspot_server_name: str | None = None,
    ip_address: str | None = None,
    hs_dst: str | None = None,
    identity: str | None = None,
):
    """Return consolidated usable-access view for a customer or device at this site."""
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    resolved_customer_id, resolved_by = await resolve_portal_customer_id(
        session,
        site_id=site.id,
        customer_id=customer_id,
        mac_address=mac_address,
    )
    if resolved_customer_id is None:
        return ok(
            {
                "site": {"id": str(site.id), "name": site.name, "slug": site.slug},
                "customer_id": None,
                "resolved_by": resolved_by,
                "has_usable_access": False,
                "primary_access": None,
                "usable_grants": [],
                "authorization": None,
            },
        )

    data = await subs_service.build_portal_access_status(session, site_id=site.id, customer_id=resolved_customer_id)
    context = build_hotspot_device_context(
        {
            "mac_address": mac_address,
            "router_id": str(router_id) if router_id else None,
            "hotspot_login_url": hotspot_login_url,
            "hotspot_server_name": hotspot_server_name,
            "ip_address": ip_address,
            "original_destination": hs_dst,
            "identity": identity,
        },
    )
    authorization = await authorize_best_portal_access(
        session,
        site=site,
        customer_id=resolved_customer_id,
        context=context,
    )
    data["customer_id"] = str(resolved_customer_id)
    data["resolved_by"] = resolved_by
    data["authorization"] = authorization
    return ok(data)


@router.post(
    "/portal/{site_slug}/session-status",
    summary="Session status by MAC",
)
async def portal_session_status(
    session: DbSession,
    site_slug: str,
    body: PortalSessionQuery = Depends(portal_rate_limit_session_body),
):
    site = (await session.execute(select(Site).where(Site.slug == site_slug))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    router_ids_sub = select(Router.id).where(Router.site_id == site.id)
    mac = body.mac_address.upper().replace("-", ":")
    s = (
        await session.execute(
            select(HotspotSession)
            .where(HotspotSession.router_id.in_(router_ids_sub), HotspotSession.mac_address == mac)
            .order_by(HotspotSession.login_at.desc())
            .limit(1),
        )
    ).scalar_one_or_none()
    if s is None:
        return ok({"active": False})
    active = s.status == SessionStatus.active.value
    return ok(
        {
            "active": active,
            "session": {
                "login_at": s.login_at.isoformat(),
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "bytes_up": s.bytes_up,
                "bytes_down": s.bytes_down,
            },
        },
    )
