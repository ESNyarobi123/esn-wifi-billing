from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SessionStatus
from app.modules.access_control.models import Role, UserRole
from app.modules.auth.models import User
from app.modules.notifications.service import notify_router_offline
from app.modules.routers.models import Router, RouterStatusSnapshot, RouterSyncLog
from app.modules.sessions.models import HotspotSession


def router_should_flip_offline(
    *,
    last_seen_at: datetime | None,
    is_online: bool,
    now: datetime,
    threshold_seconds: int,
) -> bool:
    """Return True when an *online* router should be marked offline (for tests and tasks)."""
    if not is_online:
        return False
    if last_seen_at is None:
        return True
    return last_seen_at < now - timedelta(seconds=threshold_seconds)


async def mark_stale_routers_offline(
    session: AsyncSession,
    *,
    threshold_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark ``is_online`` false when ``last_seen_at`` is older than threshold; notify admins on transition."""
    ts = now or datetime.now(UTC)
    stmt = select(Router).where(Router.status != "deleted")
    routers = (await session.execute(stmt)).scalars().all()
    transitioned: list[Router] = []
    for r in routers:
        if router_should_flip_offline(
            last_seen_at=r.last_seen_at,
            is_online=r.is_online,
            now=ts,
            threshold_seconds=threshold_seconds,
        ):
            r.is_online = False
            transitioned.append(r)
    admin_ids = (
        await session.execute(
            select(User.id)
            .distinct()
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == "admin", User.is_active.is_(True)),
        )
    ).scalars().all()
    notified = 0
    for r in transitioned:
        for uid in admin_ids:
            await notify_router_offline(session, user_id=uid, router_name=r.name, router_id=r.id)
            notified += 1
    await session.flush()
    return {"checked": len(routers), "marked_offline": len(transitioned), "notifications": notified}


async def latest_successful_sync_at(session: AsyncSession, router_id: uuid.UUID) -> datetime | None:
    row = (
        await session.execute(
            select(RouterSyncLog.finished_at)
            .where(RouterSyncLog.router_id == router_id, RouterSyncLog.status == "success")
            .order_by(desc(RouterSyncLog.finished_at))
            .limit(1),
        )
    ).scalar_one_or_none()
    return row


async def get_router_operational_overview(session: AsyncSession, router_id: uuid.UUID) -> dict[str, Any] | None:
    r = (await session.execute(select(Router).where(Router.id == router_id))).scalar_one_or_none()
    if r is None or r.status == "deleted":
        return None
    snap = (
        await session.execute(
            select(RouterStatusSnapshot)
            .where(RouterStatusSnapshot.router_id == r.id)
            .order_by(desc(RouterStatusSnapshot.created_at))
            .limit(1),
        )
    ).scalar_one_or_none()
    last_sync = await latest_successful_sync_at(session, r.id)
    active_cnt = int(
        (
            await session.execute(
                select(func.count()).select_from(HotspotSession).where(
                    HotspotSession.router_id == r.id,
                    HotspotSession.status == SessionStatus.active.value,
                ),
            )
        ).scalar_one(),
    )
    latest = None
    if snap:
        latest = {
            "cpu_load_percent": snap.cpu_load_percent,
            "free_memory_bytes": snap.free_memory_bytes,
            "total_memory_bytes": snap.total_memory_bytes,
            "uptime_seconds": snap.uptime_seconds,
            "created_at": snap.created_at.isoformat(),
        }
    return {
        "router_id": str(r.id),
        "name": r.name,
        "site_id": str(r.site_id),
        "is_online": r.is_online,
        "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
        "active_sessions": active_cnt,
        "latest_snapshot": latest,
    }


async def list_router_snapshots(
    session: AsyncSession,
    router_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(RouterStatusSnapshot)
            .where(RouterStatusSnapshot.router_id == router_id)
            .order_by(desc(RouterStatusSnapshot.created_at))
            .limit(limit),
        )
    ).scalars().all()
    return [
        {
            "id": str(s.id),
            "cpu_load_percent": s.cpu_load_percent,
            "free_memory_bytes": s.free_memory_bytes,
            "total_memory_bytes": s.total_memory_bytes,
            "uptime_seconds": s.uptime_seconds,
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]
