from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.responses import ok
from app.db.enums import PlanType
from app.modules.access_control.constants import PERM_PLANS_READ, PERM_PLANS_WRITE
from app.modules.auth.models import User
from app.modules.plans.models import Plan, PlanRouterAvailability

router = APIRouter()


class PlanCreate(BaseModel):
    name: str
    description: str | None = None
    plan_type: str = PlanType.time.value
    duration_seconds: int | None = None
    data_bytes_quota: int | None = None
    bandwidth_up_kbps: int | None = None
    bandwidth_down_kbps: int | None = None
    price_amount: Decimal = Field(ge=Decimal("0"))
    currency: str = "TZS"


class PlanRouterBody(BaseModel):
    router_ids: list[uuid.UUID]


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    plan_type: str | None = None
    duration_seconds: int | None = None
    data_bytes_quota: int | None = None
    bandwidth_up_kbps: int | None = None
    bandwidth_down_kbps: int | None = None
    price_amount: Decimal | None = None
    currency: str | None = None
    is_active: bool | None = None
    status: str | None = None


@router.get("/plans/{plan_id}", dependencies=[Depends(require_permissions(PERM_PLANS_READ))])
async def get_plan(session: DbSession, plan_id: uuid.UUID, _u: User = Depends(get_current_user)):
    p = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if p is None:
        raise NotFoundError("Plan not found")
    links = (
        await session.execute(select(PlanRouterAvailability.router_id).where(PlanRouterAvailability.plan_id == plan_id))
    ).scalars().all()
    return ok(
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "plan_type": p.plan_type,
            "duration_seconds": p.duration_seconds,
            "data_bytes_quota": p.data_bytes_quota,
            "bandwidth_up_kbps": p.bandwidth_up_kbps,
            "bandwidth_down_kbps": p.bandwidth_down_kbps,
            "price_amount": str(p.price_amount),
            "currency": p.currency,
            "is_active": p.is_active,
            "status": p.status,
            "router_ids": [str(r) for r in links],
        },
    )


@router.patch("/plans/{plan_id}", dependencies=[Depends(require_permissions(PERM_PLANS_WRITE))])
async def update_plan(session: DbSession, plan_id: uuid.UUID, body: PlanUpdate, _u: User = Depends(get_current_user)):
    p = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if p is None:
        raise NotFoundError("Plan not found")
    if body.plan_type is not None:
        if body.plan_type not in (PlanType.time.value, PlanType.data.value, PlanType.unlimited.value):
            raise ValidationAppError("Invalid plan_type")
        p.plan_type = body.plan_type
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.duration_seconds is not None:
        p.duration_seconds = body.duration_seconds
    if body.data_bytes_quota is not None:
        p.data_bytes_quota = body.data_bytes_quota
    if body.bandwidth_up_kbps is not None:
        p.bandwidth_up_kbps = body.bandwidth_up_kbps
    if body.bandwidth_down_kbps is not None:
        p.bandwidth_down_kbps = body.bandwidth_down_kbps
    if body.price_amount is not None:
        if body.price_amount < 0:
            raise ValidationAppError("price_amount must be >= 0")
        p.price_amount = body.price_amount
    if body.currency is not None:
        p.currency = body.currency
    if body.is_active is not None:
        p.is_active = body.is_active
    if body.status is not None:
        p.status = body.status
    pt = p.plan_type
    if pt == PlanType.time.value and not p.duration_seconds:
        raise ValidationAppError("time plan requires duration_seconds")
    if pt == PlanType.data.value and not p.data_bytes_quota:
        raise ValidationAppError("data plan requires data_bytes_quota")
    return ok(message="Plan updated")


@router.get("/plans", dependencies=[Depends(require_permissions(PERM_PLANS_READ))])
async def list_plans(session: DbSession, _u: User = Depends(get_current_user)):
    rows = (await session.execute(select(Plan).order_by(Plan.name))).scalars().all()
    return ok(
        [
            {
                "id": str(p.id),
                "name": p.name,
                "plan_type": p.plan_type,
                "price_amount": str(p.price_amount),
                "currency": p.currency,
                "is_active": p.is_active,
            }
            for p in rows
        ],
    )


@router.post("/plans", dependencies=[Depends(require_permissions(PERM_PLANS_WRITE))])
async def create_plan(session: DbSession, body: PlanCreate, _u: User = Depends(get_current_user)):
    if body.plan_type not in (PlanType.time.value, PlanType.data.value, PlanType.unlimited.value):
        raise ValidationAppError("Invalid plan_type")
    if body.plan_type == PlanType.time.value and not body.duration_seconds:
        raise ValidationAppError("time plan requires duration_seconds")
    if body.plan_type == PlanType.data.value and not body.data_bytes_quota:
        raise ValidationAppError("data plan requires data_bytes_quota")
    p = Plan(
        name=body.name,
        description=body.description,
        plan_type=body.plan_type,
        duration_seconds=body.duration_seconds,
        data_bytes_quota=body.data_bytes_quota,
        bandwidth_up_kbps=body.bandwidth_up_kbps,
        bandwidth_down_kbps=body.bandwidth_down_kbps,
        price_amount=body.price_amount,
        currency=body.currency,
    )
    session.add(p)
    await session.flush()
    return ok({"id": str(p.id)}, message="Plan created")


@router.put("/plans/{plan_id}/routers", dependencies=[Depends(require_permissions(PERM_PLANS_WRITE))])
async def set_plan_routers(session: DbSession, plan_id: uuid.UUID, body: PlanRouterBody, _u: User = Depends(get_current_user)):
    plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan not found")
    await session.execute(delete(PlanRouterAvailability).where(PlanRouterAvailability.plan_id == plan_id))
    for rid in body.router_ids:
        session.add(PlanRouterAvailability(plan_id=plan_id, router_id=rid))
    await session.flush()
    return ok(message="Availability updated")
