"""Pull active hotspot sessions from all NAS devices into ``hotspot_sessions`` (async SQLAlchemy)."""

from __future__ import annotations

import asyncio
import logging

from celery import current_task, shared_task
from sqlalchemy import select

from app.core.logging import get_logger, log_extra
from app.db.session import async_session_factory
from app.integrations.mikrotik.factory import get_mikrotik_adapter
from app.modules.routers.models import Router
from app.modules.sessions.service import ingest_hotspot_sessions_from_router

log = get_logger(__name__)


@shared_task(name="esn.routers.ingest_hotspot_sessions")
def ingest_hotspot_sessions_all() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        async with async_session_factory() as session:
            try:
                task_id = getattr(getattr(current_task, "request", None), "id", None)
                routers = (
                    await session.execute(select(Router).where(Router.status != "deleted"))
                ).scalars().all()
                totals = {"created": 0, "updated": 0, "pruned": 0, "routers": 0}
                for r in routers:
                    adapter = get_mikrotik_adapter(r)
                    live = await adapter.fetch_active_sessions()
                    stats = await ingest_hotspot_sessions_from_router(
                        session,
                        router_id=r.id,
                        live_rows=live,
                        prune_missing=False,
                    )
                    totals["created"] += stats["created"]
                    totals["updated"] += stats["updated"]
                    totals["pruned"] += stats["pruned"]
                    totals["routers"] += 1
                    log_extra(
                        log,
                        logging.INFO,
                        "hotspot_ingest_router",
                        task_id=task_id,
                        router_id=str(r.id),
                        created=stats["created"],
                        updated=stats["updated"],
                        pruned=stats["pruned"],
                        live=len(live),
                    )
                await session.commit()
                log_extra(
                    log,
                    logging.INFO,
                    "hotspot_ingest_complete",
                    task_id=task_id,
                    **{k: int(totals[k]) for k in ("created", "updated", "pruned", "routers")},
                )
                return totals
            except Exception:
                await session.rollback()
                log.exception(
                    "hotspot_ingest_failed task_id=%r",
                    getattr(getattr(current_task, "request", None), "id", None),
                )
                raise

    return asyncio.run(_run())

