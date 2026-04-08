from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

from app.db.sync_session import sync_session_scope
from app.integrations.mikrotik.factory import get_mikrotik_adapter
from app.modules.routers.models import Router, RouterStatusSnapshot, RouterSyncLog


@shared_task(name="esn.routers.sync_all")
def sync_all_routers() -> str:
    with sync_session_scope() as session:
        routers = list(session.execute(select(Router)).scalars().all())
        for r in routers:
            log = RouterSyncLog(router_id=r.id, started_at=datetime.now(UTC), status="running")
            session.add(log)
            session.flush()
            try:
                adapter = get_mikrotik_adapter(r)
                resources = asyncio.run(adapter.fetch_system_resources())
                snap = RouterStatusSnapshot(
                    router_id=r.id,
                    cpu_load_percent=float(resources.get("cpu_load_percent") or 0),
                    free_memory_bytes=resources.get("free_memory_bytes"),
                    total_memory_bytes=resources.get("total_memory_bytes"),
                    uptime_seconds=resources.get("uptime_seconds"),
                    raw=resources,
                )
                session.add(snap)
                r.is_online = True
                r.last_seen_at = datetime.now(UTC)
                log.status = "success"
            except Exception as exc:  # noqa: BLE001
                log.status = "error"
                log.message = str(exc)
                r.is_online = False
            log.finished_at = datetime.now(UTC)
        return f"synced {len(routers)} routers"
