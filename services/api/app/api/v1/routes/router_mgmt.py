from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.core.config import settings
from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.responses import ok
from app.core.security import encrypt_secret
from app.modules.access_control.audit_service import record_audit
from app.modules.routers.router_operations import (
    execute_block_mac,
    execute_disconnect_user,
    execute_fetch_live_sessions,
    execute_ingest_sessions,
    execute_reconcile_access_lists,
    execute_sync_router,
    execute_test_connection,
    execute_unblock_mac,
    execute_whitelist_add,
    execute_whitelist_remove,
)
from app.modules.access_control.constants import (
    PERM_DEVICES_BLOCK,
    PERM_ROUTERS_READ,
    PERM_ROUTERS_SYNC,
    PERM_ROUTERS_WRITE,
)
from app.modules.auth.models import User
from app.modules.portal.models import PortalBranding
from app.modules.routers.monitoring_service import get_router_operational_overview, list_router_snapshots
from app.modules.routers.models import Router, RouterSyncLog, Site
from app.modules.routers.provisioning_service import (
    RouterProvisioningOptions,
    build_router_provisioning_package,
)
from app.modules.routers.provisioning_push_service import push_provisioning_package_to_router
from app.modules.settings.models import SystemSetting
from app.modules.sessions.models import BlockedDevice, WhitelistedDevice

router = APIRouter()


class RouterCreate(BaseModel):
    site_id: uuid.UUID
    name: str
    host: str
    api_port: int = Field(default_factory=lambda: settings.mikrotik_default_api_port)
    username: str
    password: str
    use_tls: bool = False


class RouterUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    api_port: int | None = None
    username: str | None = None
    password: str | None = None
    use_tls: bool | None = None
    status: str | None = None


class WhitelistAddBody(BaseModel):
    mac_address: str = Field(min_length=5)
    note: str | None = None


class RouterProvisioningRequest(BaseModel):
    portal_base_url: str | None = None
    api_base_url: str | None = None
    dns_name: str | None = None
    hotspot_interface: str = "bridge-hotspot"
    wan_interface: str = "ether1"
    lan_cidr: str = "10.10.10.1/24"
    dhcp_pool_start: str = "10.10.10.10"
    dhcp_pool_end: str = "10.10.10.250"
    hotspot_html_directory: str | None = None
    hotspot_server_name: str | None = None
    hotspot_profile_name: str | None = None
    hotspot_user_profile_name: str | None = None
    address_pool_name: str | None = None
    dhcp_server_name: str | None = None
    ssl_certificate_name: str | None = None
    extra_walled_garden_hosts: list[str] = Field(default_factory=list)
    provider_templates: list[str] = Field(default_factory=list)
    auto_dns_static: bool = True
    auto_issue_letsencrypt: bool = False


@router.get(
    "/routers/{router_id}/status",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))],
)
async def router_operational_status(session: DbSession, router_id: uuid.UUID, _u: User = Depends(get_current_user)):
    data = await get_router_operational_overview(session, router_id)
    if data is None:
        raise NotFoundError("Router not found")
    return ok(data)


@router.get(
    "/routers/{router_id}/snapshots",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))],
)
async def router_status_snapshots(
    session: DbSession,
    router_id: uuid.UUID,
    _u: User = Depends(get_current_user),
    limit: int = 50,
):
    r = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if r is None or r.status == "deleted":
        raise NotFoundError("Router not found")
    rows = await list_router_snapshots(session, router_id, limit=limit)
    return ok(rows)


@router.get("/routers/{router_id}", dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))])
async def get_router(session: DbSession, router_id: uuid.UUID, _u: User = Depends(get_current_user)):
    r = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Router not found")
    return ok(
        {
            "id": str(r.id),
            "site_id": str(r.site_id),
            "name": r.name,
            "host": r.host,
            "api_port": r.api_port,
            "username": r.username,
            "use_tls": r.use_tls,
            "status": r.status,
            "is_online": r.is_online,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
        },
    )


@router.patch("/routers/{router_id}", dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))])
async def update_router(session: DbSession, router_id: uuid.UUID, body: RouterUpdate, admin: User = Depends(get_current_user)):
    r = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Router not found")
    if body.name is not None:
        r.name = body.name
    if body.host is not None:
        r.host = body.host
    if body.api_port is not None:
        r.api_port = body.api_port
    if body.username is not None:
        r.username = body.username
    if body.password is not None:
        try:
            r.password_encrypted = encrypt_secret(body.password)
        except RuntimeError as e:
            raise ValidationAppError(str(e)) from e
    if body.use_tls is not None:
        r.use_tls = body.use_tls
    if body.status is not None:
        r.status = body.status
    await record_audit(session, user_id=admin.id, action="router.update", resource_type="router", resource_id=str(router_id))
    return ok(message="Router updated")


@router.delete("/routers/{router_id}", dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))])
async def delete_router(session: DbSession, router_id: uuid.UUID, admin: User = Depends(get_current_user)):
    r = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Router not found")
    r.status = "deleted"
    await record_audit(session, user_id=admin.id, action="router.delete", resource_type="router", resource_id=str(router_id))
    return ok(message="Router marked deleted")


@router.get("/routers/{router_id}/sync-logs", dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))])
async def list_sync_logs(session: DbSession, router_id: uuid.UUID, _u: User = Depends(get_current_user), limit: int = 50):
    rows = (
        await session.execute(
            select(RouterSyncLog)
            .where(RouterSyncLog.router_id == router_id)
            .order_by(desc(RouterSyncLog.started_at))
            .limit(limit),
        )
    ).scalars().all()
    return ok(
        [
            {
                "id": str(x.id),
                "started_at": x.started_at.isoformat(),
                "finished_at": x.finished_at.isoformat() if x.finished_at else None,
                "status": x.status,
                "message": x.message,
                "stats": x.stats,
            }
            for x in rows
        ],
    )


@router.get("/routers", dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))])
async def list_routers(session: DbSession, _u: User = Depends(get_current_user), include_deleted: bool = False):
    stmt = select(Router).order_by(Router.name)
    if not include_deleted:
        stmt = stmt.where(Router.status != "deleted")
    rows = (await session.execute(stmt)).scalars().all()
    return ok(
        [
            {
                "id": str(r.id),
                "site_id": str(r.site_id),
                "name": r.name,
                "host": r.host,
                "api_port": r.api_port,
                "use_tls": r.use_tls,
                "status": r.status,
                "is_online": r.is_online,
                "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
            }
            for r in rows
        ],
    )


@router.post("/routers", dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))])
async def create_router(session: DbSession, body: RouterCreate, admin: User = Depends(get_current_user)):
    try:
        enc = encrypt_secret(body.password)
    except RuntimeError as e:
        raise ValidationAppError(str(e)) from e
    r = Router(
        site_id=body.site_id,
        name=body.name,
        host=body.host,
        api_port=body.api_port,
        username=body.username,
        password_encrypted=enc,
        use_tls=body.use_tls,
    )
    session.add(r)
    await session.flush()
    await record_audit(session, user_id=admin.id, action="router.create", resource_type="router", resource_id=str(r.id))
    return ok({"id": str(r.id)}, message="Router created")


@router.post("/routers/{router_id}/test-connection", dependencies=[Depends(require_permissions(PERM_ROUTERS_SYNC))])
async def test_router(session: DbSession, router_id: uuid.UUID, admin: User = Depends(get_current_user)):
    result = await execute_test_connection(session, router_id=router_id, admin=admin)
    return ok(result)


@router.post(
    "/routers/{router_id}/provisioning-package",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))],
    summary="Generate RouterOS provisioning package",
)
async def router_provisioning_package(
    request: Request,
    session: DbSession,
    router_id: uuid.UUID,
    body: RouterProvisioningRequest,
    admin: User = Depends(get_current_user),
):
    router_row = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if router_row is None or router_row.status == "deleted":
        raise NotFoundError("Router not found")

    site = (await session.execute(select(Site).where(Site.id == router_row.site_id))).scalar_one_or_none()
    if site is None or site.status == "deleted":
        raise NotFoundError("Router site not found")

    branding = (
        await session.execute(select(PortalBranding).where(PortalBranding.site_id == site.id))
    ).scalar_one_or_none()

    rows = (
        await session.execute(
            select(SystemSetting).where(SystemSetting.key.in_(("company_name", "support_email"))),
        )
    ).scalars().all()
    public_settings = {row.key: row.value for row in rows}

    origin = request.headers.get("origin")
    package = build_router_provisioning_package(
        router=router_row,
        site=site,
        branding=branding,
        public_settings=public_settings,
        options=RouterProvisioningOptions(
            portal_base_url=body.portal_base_url or origin,
            api_base_url=body.api_base_url or str(request.base_url).rstrip("/"),
            dns_name=body.dns_name,
            hotspot_interface=body.hotspot_interface,
            wan_interface=body.wan_interface,
            lan_cidr=body.lan_cidr,
            dhcp_pool_start=body.dhcp_pool_start,
            dhcp_pool_end=body.dhcp_pool_end,
            hotspot_html_directory=body.hotspot_html_directory,
            hotspot_server_name=body.hotspot_server_name,
            hotspot_profile_name=body.hotspot_profile_name,
            hotspot_user_profile_name=body.hotspot_user_profile_name,
            address_pool_name=body.address_pool_name,
            dhcp_server_name=body.dhcp_server_name,
            ssl_certificate_name=body.ssl_certificate_name,
            extra_walled_garden_hosts=tuple(body.extra_walled_garden_hosts),
            provider_templates=tuple(body.provider_templates),
            auto_dns_static=body.auto_dns_static,
            auto_issue_letsencrypt=body.auto_issue_letsencrypt,
        ),
    )
    await record_audit(
        session,
        user_id=admin.id,
        action="router.generate_provisioning_package",
        resource_type="router",
        resource_id=str(router_id),
    )
    return Response(
        content=package.payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{package.filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/routers/{router_id}/push-provisioning",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))],
    summary="Push provisioning package directly to router",
)
async def push_router_provisioning(
    request: Request,
    session: DbSession,
    router_id: uuid.UUID,
    body: RouterProvisioningRequest,
    admin: User = Depends(get_current_user),
):
    router_row = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if router_row is None or router_row.status == "deleted":
        raise NotFoundError("Router not found")

    site = (await session.execute(select(Site).where(Site.id == router_row.site_id))).scalar_one_or_none()
    if site is None or site.status == "deleted":
        raise NotFoundError("Router site not found")

    branding = (
        await session.execute(select(PortalBranding).where(PortalBranding.site_id == site.id))
    ).scalar_one_or_none()

    rows = (
        await session.execute(
            select(SystemSetting).where(SystemSetting.key.in_(("company_name", "support_email"))),
        )
    ).scalars().all()
    public_settings = {row.key: row.value for row in rows}
    origin = request.headers.get("origin")
    package = build_router_provisioning_package(
        router=router_row,
        site=site,
        branding=branding,
        public_settings=public_settings,
        options=RouterProvisioningOptions(
            portal_base_url=body.portal_base_url or origin,
            api_base_url=body.api_base_url or str(request.base_url).rstrip("/"),
            dns_name=body.dns_name,
            hotspot_interface=body.hotspot_interface,
            wan_interface=body.wan_interface,
            lan_cidr=body.lan_cidr,
            dhcp_pool_start=body.dhcp_pool_start,
            dhcp_pool_end=body.dhcp_pool_end,
            hotspot_html_directory=body.hotspot_html_directory,
            hotspot_server_name=body.hotspot_server_name,
            hotspot_profile_name=body.hotspot_profile_name,
            hotspot_user_profile_name=body.hotspot_user_profile_name,
            address_pool_name=body.address_pool_name,
            dhcp_server_name=body.dhcp_server_name,
            ssl_certificate_name=body.ssl_certificate_name,
            extra_walled_garden_hosts=tuple(body.extra_walled_garden_hosts),
            provider_templates=tuple(body.provider_templates),
            auto_dns_static=body.auto_dns_static,
            auto_issue_letsencrypt=body.auto_issue_letsencrypt,
        ),
    )
    result = await push_provisioning_package_to_router(router=router_row, package=package)
    await record_audit(
        session,
        user_id=admin.id,
        action="router.push_provisioning_package",
        resource_type="router",
        resource_id=str(router_id),
        details={"uploaded_count": result["uploaded_count"], "imported": result["imported"]},
    )
    return ok(result, message="Provisioning pushed to router")


@router.post(
    "/routers/{router_id}/sync",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_SYNC))],
    summary="Sync router health snapshot",
    description="Fetches NAS system resources; on failure returns ``nas`` error blob and failed sync log (no snapshot).",
)
async def sync_router(session: DbSession, router_id: uuid.UUID, admin: User = Depends(get_current_user)):
    result = await execute_sync_router(session, router_id=router_id, admin=admin)
    return ok(result)


@router.get(
    "/routers/{router_id}/sessions",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))],
    summary="Live hotspot sessions",
    description="Returns ``sessions`` from NAS plus normalized ``nas`` status (same shape as sync/ingest).",
)
async def router_live_sessions(session: DbSession, router_id: uuid.UUID, admin: User = Depends(get_current_user)):
    result = await execute_fetch_live_sessions(session, router_id=router_id, admin=admin)
    return ok(result)


@router.post(
    "/routers/{router_id}/disconnect",
    dependencies=[Depends(require_permissions(PERM_ROUTERS_SYNC))],
    summary="Disconnect hotspot session",
    openapi_extra={
        "parameters": [
            {"name": "mac", "in": "query", "schema": {"type": "string"}, "example": "AA:BB:CC:DD:EE:01"},
            {"name": "session_id", "in": "query", "schema": {"type": "string"}},
        ]
    },
)
async def router_disconnect(
    session: DbSession,
    router_id: uuid.UUID,
    mac: str | None = None,
    session_id: str | None = None,
    admin: User = Depends(get_current_user),
):
    result = await execute_disconnect_user(
        session,
        router_id=router_id,
        admin=admin,
        mac=mac,
        session_id=session_id,
    )
    return ok(result)


@router.post("/routers/{router_id}/block-mac", dependencies=[Depends(require_permissions(PERM_DEVICES_BLOCK))])
async def block_mac_route(
    session: DbSession,
    router_id: uuid.UUID,
    mac: str = Query(..., min_length=5),
    admin: User = Depends(get_current_user),
):
    result = await execute_block_mac(session, router_id=router_id, admin=admin, mac=mac)
    return ok(result, message="Blocked (adapter + local record)")


@router.post("/routers/{router_id}/unblock-mac", dependencies=[Depends(require_permissions(PERM_DEVICES_BLOCK))])
async def unblock_mac_route(
    session: DbSession,
    router_id: uuid.UUID,
    mac: str = Query(..., min_length=5),
    admin: User = Depends(get_current_user),
):
    result = await execute_unblock_mac(session, router_id=router_id, admin=admin, mac=mac)
    return ok(result, message="Unblocked on adapter")


@router.post("/routers/{router_id}/reconcile-access-lists", dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))])
async def reconcile_router_access_lists(
    session: DbSession,
    router_id: uuid.UUID,
    admin: User = Depends(get_current_user),
):
    result = await execute_reconcile_access_lists(session, router_id=router_id, admin=admin)
    return ok(result, message="Router access lists reconciled")


@router.post("/routers/{router_id}/ingest-sessions", dependencies=[Depends(require_permissions(PERM_ROUTERS_SYNC))])
async def ingest_router_sessions(
    session: DbSession,
    router_id: uuid.UUID,
    admin: User = Depends(get_current_user),
    prune_missing: bool = False,
):
    result = await execute_ingest_sessions(
        session,
        router_id=router_id,
        admin=admin,
        prune_missing=prune_missing,
    )
    return ok(result)


@router.get("/routers/{router_id}/blocked-devices", dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))])
async def list_blocked_devices(
    session: DbSession,
    router_id: uuid.UUID,
    _u: User = Depends(get_current_user),
    limit: int = 200,
):
    rows = (
        await session.execute(
            select(BlockedDevice).where(BlockedDevice.router_id == router_id).limit(limit),
        )
    ).scalars().all()
    return ok(
        [{"id": str(b.id), "mac_address": b.mac_address, "reason": b.reason, "status": b.status} for b in rows],
    )


@router.get("/routers/{router_id}/whitelisted-devices", dependencies=[Depends(require_permissions(PERM_ROUTERS_READ))])
async def list_whitelisted_devices(
    session: DbSession,
    router_id: uuid.UUID,
    _u: User = Depends(get_current_user),
    limit: int = 200,
):
    rows = (
        await session.execute(
            select(WhitelistedDevice).where(WhitelistedDevice.router_id == router_id).limit(limit),
        )
    ).scalars().all()
    return ok(
        [{"id": str(w.id), "mac_address": w.mac_address, "note": w.note} for w in rows],
    )


@router.post("/routers/{router_id}/whitelisted-devices", dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))])
async def add_whitelisted_device(
    session: DbSession,
    router_id: uuid.UUID,
    body: WhitelistAddBody,
    admin: User = Depends(get_current_user),
):
    result = await execute_whitelist_add(
        session,
        router_id=router_id,
        admin=admin,
        mac_address=body.mac_address,
        note=body.note,
    )
    return ok({"id": result["id"]}, message="Whitelisted")


@router.delete("/whitelisted-devices/{entry_id}", dependencies=[Depends(require_permissions(PERM_ROUTERS_WRITE))])
async def remove_whitelisted_device(session: DbSession, entry_id: uuid.UUID, admin: User = Depends(get_current_user)):
    await execute_whitelist_remove(session, entry_id=entry_id, admin=admin)
    return ok(message="Removed")
