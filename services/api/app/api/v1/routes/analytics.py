from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.responses import ok
from app.modules.access_control.constants import PERM_ANALYTICS_READ
from app.modules.analytics import service as analytics_service
from app.modules.auth.models import User

router = APIRouter()


@router.get("/analytics/overview", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def analytics_overview(
    session: DbSession,
    _u: User = Depends(get_current_user),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
    router_id: uuid.UUID | None = None,
):
    data = await analytics_service.analytics_overview(
        session,
        date_from=date_from,
        date_to=date_to,
        site_id=site_id,
        router_id=router_id,
    )
    return ok(data)


@router.get("/analytics/revenue", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def analytics_revenue(
    session: DbSession,
    _u: User = Depends(get_current_user),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
):
    data = await analytics_service.revenue_summary(session, date_from=date_from, date_to=date_to, site_id=site_id)
    return ok(data)


@router.get("/analytics/plans", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def analytics_plans(
    session: DbSession,
    _u: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
):
    rows = await analytics_service.top_selling_plans(
        session,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        site_id=site_id,
    )
    return ok(rows)


@router.get("/analytics/routers", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def analytics_routers(
    session: DbSession,
    _u: User = Depends(get_current_user),
    site_id: uuid.UUID | None = None,
):
    rows = await analytics_service.router_performance_summary(session, site_id=site_id)
    return ok(rows)


@router.get("/analytics/sessions", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def analytics_sessions(
    session: DbSession,
    _u: User = Depends(get_current_user),
    router_id: uuid.UUID | None = None,
):
    data = await analytics_service.sessions_summary(session, router_id=router_id)
    return ok(data)


@router.get("/analytics/summary", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def analytics_summary_legacy(session: DbSession, _u: User = Depends(get_current_user)):
    """Backward-compatible month-to-date snapshot (subset of :func:`analytics_overview`)."""
    data = await analytics_service.analytics_overview(session)
    rev = data["revenue"]
    sess = data["sessions"]
    return ok(
        {
            "revenue_month_to_date": rev["month_to_date"],
            "active_sessions": sess["active"],
            "expired_sessions": sess["expired"],
        },
    )


@router.get("/analytics/top-plans", dependencies=[Depends(require_permissions(PERM_ANALYTICS_READ))])
async def top_plans_legacy(session: DbSession, _u: User = Depends(get_current_user), limit: int = 5):
    rows = await analytics_service.top_selling_plans(session, limit=limit)
    return ok(rows)
