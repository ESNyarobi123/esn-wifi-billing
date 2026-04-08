from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import AccessGrantStatus, AccountStatus, RecordStatus
from app.integrations.mikrotik.commands import build_rate_limit, normalize_mac
from app.integrations.mikrotik.errors import MikrotikIntegrationError
from app.integrations.mikrotik.factory import get_mikrotik_adapter
from app.integrations.mikrotik.results import nas_fail, nas_ok
from app.modules.customers.models import Customer, CustomerDevice
from app.modules.plans.models import Plan
from app.modules.routers.models import Router, Site
from app.modules.subscriptions.models import CustomerAccessGrant
from app.modules.subscriptions.service import compute_grant_entitlement


@dataclass(slots=True)
class HotspotDeviceContext:
    mac_address: str
    router_id: uuid.UUID | None = None
    hotspot_login_url: str | None = None
    hotspot_server_name: str | None = None
    ip_address: str | None = None
    identity: str | None = None
    original_destination: str | None = None


def build_hotspot_device_context(raw: dict[str, Any] | None) -> HotspotDeviceContext | None:
    if not isinstance(raw, dict):
        return None
    mac = normalize_mac(raw.get("mac_address") or raw.get("hs_mac"))
    if not mac:
        return None
    router_id_raw = raw.get("router_id") or raw.get("esn_router_id")
    router_id: uuid.UUID | None = None
    if router_id_raw:
        try:
            router_id = uuid.UUID(str(router_id_raw))
        except ValueError:
            router_id = None
    return HotspotDeviceContext(
        mac_address=mac,
        router_id=router_id,
        hotspot_login_url=str(raw.get("hotspot_login_url") or raw.get("hs_login_url") or "").strip() or None,
        hotspot_server_name=str(raw.get("hotspot_server_name") or raw.get("hs_server") or "").strip() or None,
        ip_address=str(raw.get("ip_address") or raw.get("hs_ip") or "").strip() or None,
        identity=str(raw.get("identity") or raw.get("hs_identity") or "").strip() or None,
        original_destination=str(raw.get("original_destination") or raw.get("hs_dst") or "").strip() or None,
    )


def normalize_portal_customer_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if digits.startswith("255") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return f"255{digits[1:]}"
    return digits


def normalize_portal_customer_email(raw: str | None) -> str | None:
    email = str(raw or "").strip().lower()
    return email or None


def _portal_customer_name(*, full_name: str | None, phone: str | None) -> str:
    cleaned = str(full_name or "").strip()
    if cleaned:
        return cleaned
    if phone:
        return f"WiFi Guest {phone[-4:]}"
    return "WiFi Guest"


def build_hotspot_username(*, grant_id: uuid.UUID, mac_address: str) -> str:
    suffix = normalize_mac(mac_address).replace(":", "")[-6:].lower()
    return f"esn-{str(grant_id)[:8]}-{suffix}"


def build_hotspot_password(*, grant_id: uuid.UUID, mac_address: str) -> str:
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        f"{grant_id}:{normalize_mac(mac_address)}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:20]


def build_hotspot_profile_name(plan: Plan) -> str:
    return f"esn-plan-{str(plan.id)[:8]}"


def grant_remaining_seconds(grant: CustomerAccessGrant, *, now: datetime | None = None) -> int | None:
    if grant.ends_at is None:
        return None
    ts = now or datetime.now(UTC)
    remaining = int((grant.ends_at - ts).total_seconds())
    return max(remaining, 0)


async def upsert_customer_device_binding(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    site_id: uuid.UUID,
    mac_address: str,
    hostname: str | None = None,
) -> CustomerDevice:
    mac = normalize_mac(mac_address)
    existing = (
        await session.execute(
            select(CustomerDevice).where(CustomerDevice.site_id == site_id, CustomerDevice.mac_address == mac),
        )
    ).scalar_one_or_none()
    if existing:
        existing.customer_id = customer_id
        if hostname:
            existing.hostname = hostname
        return existing
    device = CustomerDevice(
        customer_id=customer_id,
        site_id=site_id,
        mac_address=mac,
        hostname=hostname,
        first_seen_at=datetime.now(UTC),
    )
    session.add(device)
    await session.flush()
    return device


async def resolve_portal_customer_id(
    session: AsyncSession,
    *,
    site_id: uuid.UUID,
    customer_id: uuid.UUID | None,
    mac_address: str | None,
) -> tuple[uuid.UUID | None, str | None]:
    if customer_id:
        return customer_id, "customer_id"
    mac = normalize_mac(mac_address)
    if not mac:
        return None, None
    device = (
        await session.execute(
            select(CustomerDevice).where(CustomerDevice.site_id == site_id, CustomerDevice.mac_address == mac),
        )
    ).scalar_one_or_none()
    if device is None:
        return None, None
    return device.customer_id, "device_mac"


async def resolve_or_create_portal_customer(
    session: AsyncSession,
    *,
    site_id: uuid.UUID,
    customer_id: uuid.UUID | None,
    mac_address: str | None,
    phone: str | None,
    email: str | None,
    full_name: str | None,
    hostname: str | None = None,
) -> tuple[uuid.UUID | None, str | None]:
    normalized_phone = normalize_portal_customer_phone(phone)
    normalized_email = normalize_portal_customer_email(email)

    resolved_customer_id, resolved_by = await resolve_portal_customer_id(
        session,
        site_id=site_id,
        customer_id=customer_id,
        mac_address=mac_address,
    )

    customer: Customer | None = None
    if resolved_customer_id:
        customer = (await session.execute(select(Customer).where(Customer.id == resolved_customer_id))).scalar_one_or_none()

    if customer is None and normalized_phone:
        phone_matches = (
            await session.execute(
                select(Customer)
                .where(
                    Customer.site_id == site_id,
                    Customer.phone == normalized_phone,
                    Customer.status != RecordStatus.deleted.value,
                )
                .order_by(Customer.created_at.desc()),
            )
        ).scalars().all()
        customer = phone_matches[0] if phone_matches else None
        if customer is not None:
            resolved_customer_id = customer.id
            resolved_by = "phone"

    if customer is None and normalized_email:
        email_matches = (
            await session.execute(
                select(Customer)
                .where(
                    Customer.site_id == site_id,
                    Customer.email == normalized_email,
                    Customer.status != RecordStatus.deleted.value,
                )
                .order_by(Customer.created_at.desc()),
            )
        ).scalars().all()
        customer = email_matches[0] if email_matches else None
        if customer is not None:
            resolved_customer_id = customer.id
            resolved_by = "email"

    if customer is None and any([normalized_phone, normalized_email, str(full_name or "").strip()]):
        customer = Customer(
            site_id=site_id,
            phone=normalized_phone,
            email=normalized_email,
            full_name=_portal_customer_name(full_name=full_name, phone=normalized_phone),
            account_status=AccountStatus.active.value,
        )
        session.add(customer)
        await session.flush()
        resolved_customer_id = customer.id
        resolved_by = "created_portal_customer"

    if customer is not None:
        if normalized_phone and not customer.phone:
            customer.phone = normalized_phone
        if normalized_email and not customer.email:
            customer.email = normalized_email
        if full_name and not str(customer.full_name or "").strip():
            customer.full_name = str(full_name).strip()
        if customer.site_id is None:
            customer.site_id = site_id
        resolved_customer_id = customer.id

    mac = normalize_mac(mac_address)
    if resolved_customer_id and mac:
        await upsert_customer_device_binding(
            session,
            customer_id=resolved_customer_id,
            site_id=site_id,
            mac_address=mac,
            hostname=hostname,
        )

    return resolved_customer_id, resolved_by


async def resolve_site_router(session: AsyncSession, *, site: Site, context: HotspotDeviceContext) -> Router | None:
    if context.router_id:
        router = (
            await session.execute(
                select(Router).where(
                    Router.id == context.router_id,
                    Router.site_id == site.id,
                    Router.status != "deleted",
                ),
            )
        ).scalar_one_or_none()
        if router:
            return router
    routers = (
        await session.execute(select(Router).where(Router.site_id == site.id, Router.status != "deleted").order_by(Router.name))
    ).scalars().all()
    if len(routers) == 1:
        return routers[0]
    return None


async def authorize_grant_for_device(
    session: AsyncSession,
    *,
    site: Site,
    router: Router,
    grant: CustomerAccessGrant,
    plan: Plan,
    context: HotspotDeviceContext,
) -> dict[str, Any]:
    entitlement = compute_grant_entitlement(grant=grant, plan=plan)
    if not entitlement.get("is_usable"):
        return {
            "available": False,
            "reason": entitlement.get("reason"),
            "nas": nas_ok(notes="grant_not_usable"),
        }

    mac = normalize_mac(context.mac_address)
    username = build_hotspot_username(grant_id=grant.id, mac_address=mac)
    password = build_hotspot_password(grant_id=grant.id, mac_address=mac)
    remaining = grant_remaining_seconds(grant)
    rate_limit = build_rate_limit(
        bandwidth_up_kbps=plan.bandwidth_up_kbps,
        bandwidth_down_kbps=plan.bandwidth_down_kbps,
    )

    try:
        adapter = get_mikrotik_adapter(router)
        payload = await adapter.ensure_hotspot_user(
            username=username,
            password=password,
            mac=mac,
            profile_name=build_hotspot_profile_name(plan),
            server=context.hotspot_server_name,
            comment=f"esn-grant:{grant.id}",
            limit_uptime_seconds=remaining,
            rate_limit=rate_limit,
        )
    except MikrotikIntegrationError as exc:
        return {
            "available": False,
            "reason": "router_authorization_failed",
            "nas": nas_fail(exc),
        }

    await upsert_customer_device_binding(
        session,
        customer_id=grant.customer_id,
        site_id=site.id,
        mac_address=mac,
        hostname=context.identity,
    )

    return {
        "available": True,
        "mode": "router_local_hotspot",
        "router_id": str(router.id),
        "router_name": router.name,
        "mac_address": mac,
        "username": username,
        "password": password,
        "profile_name": payload["profile_name"],
        "rate_limit": payload.get("rate_limit"),
        "limit_uptime_seconds": remaining,
        "login_url": context.hotspot_login_url,
        "server_name": context.hotspot_server_name,
        "destination": context.original_destination,
        "nas": nas_ok(),
    }


async def authorize_best_portal_access(
    session: AsyncSession,
    *,
    site: Site,
    customer_id: uuid.UUID,
    context: HotspotDeviceContext | None,
) -> dict[str, Any] | None:
    if context is None:
        return None
    router = await resolve_site_router(session, site=site, context=context)
    if router is None:
        return {
            "available": False,
            "reason": "router_context_missing",
            "nas": nas_ok(notes="router_not_resolved"),
        }

    grants = (
        await session.execute(
            select(CustomerAccessGrant)
            .where(CustomerAccessGrant.customer_id == customer_id)
            .order_by(CustomerAccessGrant.starts_at.desc()),
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for grant in grants:
        if grant.site_id is not None and grant.site_id != site.id:
            continue
        plan = (await session.execute(select(Plan).where(Plan.id == grant.plan_id))).scalar_one_or_none()
        if plan is None:
            continue
        entitlement = compute_grant_entitlement(grant=grant, plan=plan, now=now)
        if not entitlement.get("is_usable"):
            continue
        return await authorize_grant_for_device(
            session,
            site=site,
            router=router,
            grant=grant,
            plan=plan,
            context=context,
        )
    return None


async def reconcile_expired_authorizations(session: AsyncSession) -> dict[str, int]:
    now = datetime.now(UTC)
    grants = (
        await session.execute(
            select(CustomerAccessGrant).where(
                CustomerAccessGrant.status == AccessGrantStatus.active.value,
                CustomerAccessGrant.ends_at.is_not(None),
                CustomerAccessGrant.ends_at <= now,
            ),
        )
    ).scalars().all()
    removed_users = 0
    disconnected = 0
    errors = 0
    grants_marked = 0
    for grant in grants:
        grant.status = AccessGrantStatus.expired.value
        grants_marked += 1
        site_id = grant.site_id
        if site_id is None:
            continue
        devices = (
            await session.execute(
                select(CustomerDevice).where(CustomerDevice.customer_id == grant.customer_id, CustomerDevice.site_id == site_id),
            )
        ).scalars().all()
        if not devices:
            continue
        routers = (
            await session.execute(select(Router).where(Router.site_id == site_id, Router.status != "deleted"))
        ).scalars().all()
        for router in routers:
            adapter = get_mikrotik_adapter(router)
            for device in devices:
                username = build_hotspot_username(grant_id=grant.id, mac_address=device.mac_address)
                try:
                    if await adapter.remove_hotspot_user(username=username):
                        removed_users += 1
                    if await adapter.disconnect_hotspot_user(mac=device.mac_address):
                        disconnected += 1
                except MikrotikIntegrationError:
                    errors += 1
    await session.flush()
    return {
        "grants_marked_expired": grants_marked,
        "removed_users": removed_users,
        "disconnected": disconnected,
        "errors": errors,
    }
