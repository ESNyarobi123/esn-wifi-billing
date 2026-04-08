"""Mark routers offline when heartbeats (``last_seen_at``) are stale."""

from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from app.core.config import settings
from app.core.logging import get_logger, log_extra
from app.db.session import async_session_factory
from app.modules.routers.monitoring_service import mark_stale_routers_offline

log = get_logger(__name__)


@shared_task(name="esn.routers.mark_offline_stale")
def mark_offline_stale() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        async with async_session_factory() as session:
            try:
                stats = await mark_stale_routers_offline(
                    session,
                    threshold_seconds=settings.router_offline_after_seconds,
                )
                await session.commit()
                log_extra(
                    log,
                    logging.INFO,
                    "router_offline_sweep_done",
                    marked_offline=stats["marked_offline"],
                    checked=stats["checked"],
                    notifications=stats["notifications"],
                )
                return {k: int(v) for k, v in stats.items() if isinstance(v, int)}
            except Exception:
                await session.rollback()
                log.exception("router_offline_sweep_failed")
                raise

    return asyncio.run(_run())
