from __future__ import annotations

import asyncio

from celery import shared_task

from app.db.session import async_session_factory
from app.modules.routers.hotspot_authorization_service import reconcile_expired_authorizations


@shared_task(name="esn.routers.reconcile_hotspot_authorizations")
def reconcile_hotspot_authorizations() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        async with async_session_factory() as session:
            try:
                stats = await reconcile_expired_authorizations(session)
                await session.commit()
                return stats
            except Exception:
                await session.rollback()
                raise

    return asyncio.run(_run())
