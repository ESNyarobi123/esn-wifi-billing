"""Operational NAS actions — adapter calls, persistence, structured results, audit (single entry point per action)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.integrations.mikrotik.errors import MikrotikIntegrationError
from app.integrations.mikrotik.factory import get_mikrotik_adapter
from app.integrations.mikrotik.results import nas_fail, nas_ok
from app.modules.access_control.audit_service import record_audit
from app.modules.auth.models import User
from app.modules.routers.models import Router, RouterStatusSnapshot, RouterSyncLog
from app.modules.sessions.models import BlockedDevice, WhitelistedDevice
from app.modules.sessions.service import ingest_hotspot_sessions_from_router


def _norm_mac(mac: str) -> str:
    return mac.upper().replace("-", ":")


async def get_router_or_error(session: AsyncSession, router_id: uuid.UUID) -> Router:
    r = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if r is None or r.status == "deleted":
        raise NotFoundError("Router not found")
    return r


async def execute_test_connection(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    adapter = get_mikrotik_adapter(r)
    nas: dict[str, Any]
    try:
        ok_conn = await adapter.test_connection()
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        ok_conn = False
        nas = nas_fail(e)
    r.is_online = bool(ok_conn)
    r.last_seen_at = datetime.now(UTC)
    await record_audit(
        session,
        user_id=admin.id,
        action="router.test_connection",
        resource_type="router",
        resource_id=str(router_id),
        details={"connected": ok_conn, "nas": nas},
    )
    return {"action": "test_connection", "router_id": str(router_id), "connected": ok_conn, "nas": nas}


async def execute_sync_router(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    started = datetime.now(UTC)
    log = RouterSyncLog(router_id=r.id, started_at=started, status="running")
    session.add(log)
    await session.flush()
    adapter = get_mikrotik_adapter(r)
    try:
        resources = await adapter.fetch_system_resources()
    except MikrotikIntegrationError as e:
        log.finished_at = datetime.now(UTC)
        log.status = "failed"
        log.message = e.message
        log.stats = {"nas": nas_fail(e)}
        await record_audit(
            session,
            user_id=admin.id,
            action="router.sync",
            resource_type="router",
            resource_id=str(router_id),
            details={"sync_log_id": str(log.id), "nas": nas_fail(e)},
        )
        return {
            "action": "sync",
            "router_id": str(router_id),
            "resources": None,
            "sync_log_id": str(log.id),
            "snapshot_id": None,
            "nas": nas_fail(e),
        }

    snap = RouterStatusSnapshot(
        router_id=r.id,
        cpu_load_percent=float(resources.get("cpu_load_percent") or 0),
        free_memory_bytes=resources.get("free_memory_bytes"),
        total_memory_bytes=resources.get("total_memory_bytes"),
        uptime_seconds=resources.get("uptime_seconds"),
        raw=resources,
    )
    session.add(snap)
    await session.flush()
    r.is_online = True
    r.last_seen_at = datetime.now(UTC)
    log.finished_at = datetime.now(UTC)
    log.status = "success"
    log.stats = {"snapshot_id": str(snap.id)}
    await record_audit(
        session,
        user_id=admin.id,
        action="router.sync",
        resource_type="router",
        resource_id=str(router_id),
        details={"sync_log_id": str(log.id), "snapshot_id": str(snap.id), "nas": nas_ok()},
    )
    return {
        "action": "sync",
        "router_id": str(router_id),
        "resources": resources,
        "sync_log_id": str(log.id),
        "snapshot_id": str(snap.id),
        "nas": nas_ok(),
    }


async def execute_disconnect_user(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
    mac: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    adapter = get_mikrotik_adapter(r)
    try:
        changed = await adapter.disconnect_hotspot_user(session_id=session_id, mac=mac)
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        changed = False
        nas = nas_fail(e)
    await record_audit(
        session,
        user_id=admin.id,
        action="router.disconnect_user",
        resource_type="router",
        resource_id=str(router_id),
        details={"mac": mac, "session_id": session_id, "disconnected": changed, "nas": nas},
    )
    return {"action": "disconnect_user", "router_id": str(router_id), "disconnected": changed, "nas": nas}


async def execute_block_mac(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
    mac: str,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    norm = _norm_mac(mac)
    adapter = get_mikrotik_adapter(r)
    try:
        await adapter.block_mac(mac=norm)
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        nas = nas_fail(e)
        await record_audit(
            session,
            user_id=admin.id,
            action="device.block",
            resource_type="router",
            resource_id=str(router_id),
            details={"mac": norm, "nas": nas, "applied": False},
        )
        return {"action": "block_mac", "router_id": str(router_id), "mac_address": norm, "applied": False, "nas": nas}
    session.add(
        BlockedDevice(
            router_id=router_id,
            mac_address=norm,
            reason="manual block",
        ),
    )
    await record_audit(
        session,
        user_id=admin.id,
        action="device.block",
        resource_type="router",
        resource_id=str(router_id),
        details={"mac": norm, "nas": nas, "applied": True},
    )
    return {"action": "block_mac", "router_id": str(router_id), "mac_address": norm, "applied": True, "nas": nas}


async def execute_unblock_mac(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
    mac: str,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    norm = _norm_mac(mac)
    adapter = get_mikrotik_adapter(r)
    try:
        await adapter.unblock_mac(mac=norm)
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        nas = nas_fail(e)
        await record_audit(
            session,
            user_id=admin.id,
            action="device.unblock",
            resource_type="router",
            resource_id=str(router_id),
            details={"mac": norm, "nas": nas, "applied": False},
        )
        return {"action": "unblock_mac", "router_id": str(router_id), "mac_address": norm, "applied": False, "nas": nas}
    await session.execute(
        delete(BlockedDevice).where(BlockedDevice.router_id == router_id, BlockedDevice.mac_address == norm),
    )
    await record_audit(
        session,
        user_id=admin.id,
        action="device.unblock",
        resource_type="router",
        resource_id=str(router_id),
        details={"mac": norm, "nas": nas, "applied": True},
    )
    return {"action": "unblock_mac", "router_id": str(router_id), "mac_address": norm, "applied": True, "nas": nas}


async def execute_ingest_sessions(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
    prune_missing: bool,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    adapter = get_mikrotik_adapter(r)
    try:
        live = await adapter.fetch_active_sessions()
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        await record_audit(
            session,
            user_id=admin.id,
            action="router.ingest_sessions",
            resource_type="router",
            resource_id=str(router_id),
            details={"nas": nas_fail(e), "ingested": 0},
        )
        return {"action": "ingest_sessions", "router_id": str(router_id), "nas": nas_fail(e), "ingested": 0, "updated": 0}
    stats = await ingest_hotspot_sessions_from_router(
        session,
        router_id=router_id,
        live_rows=live,
        prune_missing=prune_missing,
    )
    merged = {**stats, "nas": nas}
    await record_audit(
        session,
        user_id=admin.id,
        action="router.ingest_sessions",
        resource_type="router",
        resource_id=str(router_id),
        details=merged,
    )
    return {"action": "ingest_sessions", "router_id": str(router_id), **merged}


async def execute_fetch_live_sessions(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
) -> dict[str, Any]:
    """Live session list (read-heavy); no audit row — use ingest/sync actions for mutating audit trails."""
    _ = admin
    r = await get_router_or_error(session, router_id)
    adapter = get_mikrotik_adapter(r)
    try:
        sessions = await adapter.fetch_active_sessions()
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        return {"action": "fetch_live_sessions", "router_id": str(router_id), "sessions": [], "nas": nas_fail(e)}
    return {"action": "fetch_live_sessions", "router_id": str(router_id), "sessions": sessions, "nas": nas}


async def execute_whitelist_add(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
    mac_address: str,
    note: str | None,
) -> dict[str, Any]:
    r = await get_router_or_error(session, router_id)
    mac = _norm_mac(mac_address)
    adapter = get_mikrotik_adapter(r)
    try:
        await adapter.whitelist_mac(mac=mac, note=note)
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        nas = nas_fail(e)
        await record_audit(
            session,
            user_id=admin.id,
            action="router.whitelist_add",
            resource_type="router",
            resource_id=str(router_id),
            details={"mac": mac, "note": note, "applied": False, "nas": nas},
        )
        return {
            "action": "whitelist_add",
            "router_id": str(router_id),
            "id": None,
            "mac_address": mac,
            "nas": nas,
        }
    w = WhitelistedDevice(router_id=router_id, mac_address=mac, note=note)
    session.add(w)
    await session.flush()
    await record_audit(
        session,
        user_id=admin.id,
        action="router.whitelist_add",
        resource_type="router",
        resource_id=str(router_id),
        details={"mac": mac, "entry_id": str(w.id), "nas": nas},
    )
    return {
        "action": "whitelist_add",
        "router_id": str(router_id),
        "id": str(w.id),
        "mac_address": mac,
        "nas": nas,
    }


async def execute_whitelist_remove(
    session: AsyncSession,
    *,
    entry_id: uuid.UUID,
    admin: User,
) -> dict[str, Any]:
    w = (await session.execute(select(WhitelistedDevice).where(WhitelistedDevice.id == entry_id))).scalar_one_or_none()
    if w is None:
        raise NotFoundError("Whitelist entry not found")
    rid = w.router_id
    router = await get_router_or_error(session, rid)
    adapter = get_mikrotik_adapter(router)
    try:
        await adapter.remove_whitelist_mac(mac=w.mac_address)
        nas = nas_ok()
    except MikrotikIntegrationError as e:
        nas = nas_fail(e)
        await record_audit(
            session,
            user_id=admin.id,
            action="router.whitelist_remove",
            resource_type="router",
            resource_id=str(rid),
            details={"entry_id": str(entry_id), "applied": False, "nas": nas},
        )
        return {"action": "whitelist_remove", "router_id": str(rid), "entry_id": str(entry_id), "nas": nas}
    await session.execute(delete(WhitelistedDevice).where(WhitelistedDevice.id == entry_id))
    await record_audit(
        session,
        user_id=admin.id,
        action="router.whitelist_remove",
        resource_type="router",
        resource_id=str(rid),
        details={"entry_id": str(entry_id), "nas": nas},
    )
    return {"action": "whitelist_remove", "router_id": str(rid), "entry_id": str(entry_id), "nas": nas}


async def execute_reconcile_access_lists(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    admin: User,
) -> dict[str, Any]:
    router = await get_router_or_error(session, router_id)
    adapter = get_mikrotik_adapter(router)
    blocked = (
        await session.execute(select(BlockedDevice).where(BlockedDevice.router_id == router_id).order_by(BlockedDevice.created_at))
    ).scalars().all()
    whitelisted = (
        await session.execute(select(WhitelistedDevice).where(WhitelistedDevice.router_id == router_id).order_by(WhitelistedDevice.created_at))
    ).scalars().all()

    whitelist_macs = {_norm_mac(item.mac_address) for item in whitelisted}
    whitelist_applied = 0
    blocked_applied = 0
    blocked_skipped = 0
    errors: list[dict[str, str]] = []

    for item in whitelisted:
        mac = _norm_mac(item.mac_address)
        try:
            await adapter.whitelist_mac(mac=mac, note=item.note)
            whitelist_applied += 1
        except MikrotikIntegrationError as exc:
            errors.append({"scope": "whitelist", "mac_address": mac, "message": exc.message, "code": exc.code})

    for item in blocked:
        mac = _norm_mac(item.mac_address)
        if mac in whitelist_macs:
            blocked_skipped += 1
            continue
        try:
            await adapter.block_mac(mac=mac)
            blocked_applied += 1
        except MikrotikIntegrationError as exc:
            errors.append({"scope": "blocked", "mac_address": mac, "message": exc.message, "code": exc.code})

    nas: dict[str, Any] = {"ok": not errors}
    if errors:
        nas["notes"] = "partial_failures"

    result = {
        "action": "reconcile_access_lists",
        "router_id": str(router_id),
        "whitelist_applied": whitelist_applied,
        "blocked_applied": blocked_applied,
        "blocked_skipped": blocked_skipped,
        "error_count": len(errors),
        "errors": errors,
        "nas": nas,
    }
    await record_audit(
        session,
        user_id=admin.id,
        action="router.reconcile_access_lists",
        resource_type="router",
        resource_id=str(router_id),
        details=result,
    )
    return result
