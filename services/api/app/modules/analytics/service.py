from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import PaymentStatus, SessionStatus
from app.modules.customers.models import Customer
from app.modules.payments.models import Payment
from app.modules.plans.models import Plan
from app.modules.routers.models import Router, RouterStatusSnapshot
from app.modules.sessions.models import HotspotSession


def _range_bounds(
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    end = date_to or now
    start = date_from or (end - timedelta(days=default_days))
    return start, end


async def revenue_summary(
    session: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def _sum(since: datetime, until: datetime | None = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.payment_status == PaymentStatus.success.value,
            Payment.created_at >= since,
        )
        if until:
            stmt = stmt.where(Payment.created_at <= until)
        if site_id:
            stmt = stmt.where(Payment.site_id == site_id)
        val = (await session.execute(stmt)).scalar_one()
        return Decimal(str(val))

    start, end = _range_bounds(date_from=date_from, date_to=date_to, default_days=30)
    period_total = await _sum(start, end)

    return {
        "today": str(await _sum(day_start)),
        "week_to_date": str(await _sum(week_start)),
        "month_to_date": str(await _sum(month_start)),
        "period": {"from": start.isoformat(), "to": end.isoformat(), "total": str(period_total)},
    }


async def sessions_summary(session: AsyncSession, *, router_id: uuid.UUID | None = None) -> dict[str, int]:
    async def _cnt(status_val: str) -> int:
        stmt = select(func.count()).select_from(HotspotSession).where(HotspotSession.status == status_val)
        if router_id:
            stmt = stmt.where(HotspotSession.router_id == router_id)
        return int((await session.execute(stmt)).scalar_one())

    active = await _cnt(SessionStatus.active.value)
    expired = await _cnt(SessionStatus.expired.value)
    terminated = await _cnt(SessionStatus.terminated.value)
    suspicious = await _cnt(SessionStatus.suspicious.value)
    return {
        "active": active,
        "expired": expired,
        "terminated": terminated,
        "suspicious": suspicious,
    }


async def top_selling_plans(
    session: AsyncSession,
    *,
    limit: int = 10,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    start, end = _range_bounds(date_from=date_from, date_to=date_to, default_days=90)
    filters = [
        Payment.payment_status == PaymentStatus.success.value,
        Payment.plan_id.isnot(None),
        Payment.created_at >= start,
        Payment.created_at <= end,
    ]
    if site_id:
        filters.append(Payment.site_id == site_id)
    stmt = (
        select(Payment.plan_id, func.count().label("cnt"))
        .where(*filters)
        .group_by(Payment.plan_id)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for pid, cnt in rows:
        if not pid:
            continue
        p = (await session.execute(select(Plan).where(Plan.id == pid))).scalar_one_or_none()
        out.append({"plan_id": str(pid), "name": p.name if p else None, "purchases": int(cnt)})
    return out


async def router_performance_summary(
    session: AsyncSession,
    *,
    site_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = select(Router).where(Router.status != "deleted")
    if site_id:
        stmt = stmt.where(Router.site_id == site_id)
    routers = (await session.execute(stmt.order_by(Router.name))).scalars().all()
    out: list[dict[str, Any]] = []
    for r in routers:
        snap = (
            await session.execute(
                select(RouterStatusSnapshot)
                .where(RouterStatusSnapshot.router_id == r.id)
                .order_by(RouterStatusSnapshot.created_at.desc())
                .limit(1),
            )
        ).scalar_one_or_none()
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
        out.append(
            {
                "router_id": str(r.id),
                "name": r.name,
                "is_online": r.is_online,
                "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
                "active_sessions": active_cnt,
                "latest_snapshot": (
                    {
                        "cpu_load_percent": snap.cpu_load_percent,
                        "free_memory_bytes": snap.free_memory_bytes,
                        "uptime_seconds": snap.uptime_seconds,
                        "created_at": snap.created_at.isoformat(),
                    }
                    if snap
                    else None
                ),
            },
        )
    return out


async def customer_growth_summary(
    session: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    start, end = _range_bounds(date_from=date_from, date_to=date_to, default_days=30)
    new_stmt = select(func.count()).select_from(Customer).where(
        Customer.created_at >= start,
        Customer.created_at <= end,
    )
    total_stmt = select(func.count()).select_from(Customer)
    if site_id:
        new_stmt = new_stmt.where(Customer.site_id == site_id)
        total_stmt = total_stmt.where(Customer.site_id == site_id)
    new_customers = int((await session.execute(new_stmt)).scalar_one())
    total_customers = int((await session.execute(total_stmt)).scalar_one())
    return {
        "new_in_period": new_customers,
        "total_customers": total_customers,
        "period": {"from": start.isoformat(), "to": end.isoformat()},
    }


async def payment_status_breakdown(session: AsyncSession, *, site_id: uuid.UUID | None = None) -> dict[str, int]:
    stmt = select(Payment.payment_status, func.count())
    if site_id:
        stmt = stmt.where(Payment.site_id == site_id)
    stmt = stmt.group_by(Payment.payment_status)
    rows = (await session.execute(stmt)).all()
    return {str(status): int(cnt) for status, cnt in rows}


async def analytics_overview(
    session: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    site_id: uuid.UUID | None = None,
    router_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    rev = await revenue_summary(session, date_from=date_from, date_to=date_to, site_id=site_id)
    sess = await sessions_summary(session, router_id=router_id)
    pay_bd = await payment_status_breakdown(session, site_id=site_id)
    cust = await customer_growth_summary(session, date_from=date_from, date_to=date_to, site_id=site_id)
    plans = await top_selling_plans(
        session,
        limit=5,
        date_from=date_from,
        date_to=date_to,
        site_id=site_id,
    )
    routers = await router_performance_summary(session, site_id=site_id)
    return {
        "revenue": rev,
        "sessions": sess,
        "payments_by_status": pay_bd,
        "customers": cust,
        "top_plans": plans,
        "routers": routers[:20],
    }
