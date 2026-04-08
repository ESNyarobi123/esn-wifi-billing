from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError
from app.core.responses import ok
from app.db.enums import VoucherStatus
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_VOUCHERS_READ, PERM_VOUCHERS_WRITE
from app.modules.auth.models import User
from app.modules.vouchers.models import Voucher, VoucherBatch
from app.modules.vouchers.redemption import redeem_voucher

router = APIRouter()


class SingleVoucherCreate(BaseModel):
    plan_id: uuid.UUID
    code: str | None = None
    pin: str | None = None
    expires_at: datetime | None = None


class BulkVoucherCreate(BaseModel):
    name: str
    plan_id: uuid.UUID
    quantity: int = Field(ge=1, le=50_000)
    prefix: str | None = Field(default=None, max_length=8)
    requires_pin: bool = False


class RedeemBody(BaseModel):
    code: str
    pin: str | None = None
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = Field(default=None, description="If set, plan must be offered at this site")


@router.get("/vouchers", dependencies=[Depends(require_permissions(PERM_VOUCHERS_READ))])
async def list_vouchers(session: DbSession, _u: User = Depends(get_current_user), limit: int = 100):
    rows = (await session.execute(select(Voucher).order_by(Voucher.created_at.desc()).limit(limit))).scalars().all()
    return ok(
        [
            {
                "id": str(v.id),
                "code": v.code,
                "status": v.status,
                "plan_id": str(v.plan_id),
                "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            }
            for v in rows
        ],
    )


@router.get("/voucher-batches/{batch_id}", dependencies=[Depends(require_permissions(PERM_VOUCHERS_READ))])
async def get_voucher_batch(session: DbSession, batch_id: uuid.UUID, _u: User = Depends(get_current_user)):
    b = (await session.execute(select(VoucherBatch).where(VoucherBatch.id == batch_id))).scalar_one_or_none()
    if b is None:
        raise NotFoundError("Batch not found")
    status_rows = (
        await session.execute(
            select(Voucher.status, func.count()).where(Voucher.batch_id == batch_id).group_by(Voucher.status),
        )
    ).all()
    by_status = {str(row[0]): int(row[1]) for row in status_rows}
    total = sum(by_status.values())
    return ok(
        {
            "id": str(b.id),
            "name": b.name,
            "plan_id": str(b.plan_id),
            "quantity": b.quantity,
            "prefix": b.prefix,
            "requires_pin": b.requires_pin,
            "status": b.status,
            "voucher_total": total,
            "vouchers_by_status": by_status,
            "created_at": b.created_at.isoformat(),
        },
    )


@router.get("/voucher-batches", dependencies=[Depends(require_permissions(PERM_VOUCHERS_READ))])
async def list_batches(session: DbSession, _u: User = Depends(get_current_user)):
    rows = (await session.execute(select(VoucherBatch).order_by(VoucherBatch.created_at.desc()))).scalars().all()
    return ok([{"id": str(b.id), "name": b.name, "quantity": b.quantity, "plan_id": str(b.plan_id)} for b in rows])


@router.post("/vouchers", dependencies=[Depends(require_permissions(PERM_VOUCHERS_WRITE))])
async def create_voucher(session: DbSession, body: SingleVoucherCreate, admin: User = Depends(get_current_user)):
    code = body.code or secrets.token_hex(4).upper()
    v = Voucher(
        plan_id=body.plan_id,
        code=code,
        pin=body.pin,
        expires_at=body.expires_at,
        status=VoucherStatus.unused.value,
    )
    session.add(v)
    await session.flush()
    await record_audit(session, user_id=admin.id, action="voucher.create", resource_type="voucher", resource_id=str(v.id))
    return ok({"id": str(v.id), "code": code}, message="Voucher created")


@router.post("/voucher-batches", dependencies=[Depends(require_permissions(PERM_VOUCHERS_WRITE))])
async def create_batch(session: DbSession, body: BulkVoucherCreate, admin: User = Depends(get_current_user)):
    batch = VoucherBatch(
        name=body.name,
        plan_id=body.plan_id,
        quantity=body.quantity,
        prefix=body.prefix,
        requires_pin=body.requires_pin,
    )
    session.add(batch)
    await session.flush()
    created = []
    for i in range(body.quantity):
        code = f"{body.prefix or 'V'}{secrets.token_hex(3).upper()}-{i:04d}"
        pin = secrets.token_hex(2) if body.requires_pin else None
        v = Voucher(
            batch_id=batch.id,
            plan_id=body.plan_id,
            code=code,
            pin=pin,
            status=VoucherStatus.unused.value,
        )
        session.add(v)
        created.append(code)
    await session.flush()
    await record_audit(
        session,
        user_id=admin.id,
        action="voucher.batch_create",
        resource_type="voucher_batch",
        resource_id=str(batch.id),
        details={"quantity": body.quantity},
    )
    return ok({"batch_id": str(batch.id), "sample_codes": created[:5]}, message="Batch created")


@router.post("/vouchers/redeem", dependencies=[Depends(require_permissions(PERM_VOUCHERS_WRITE))])
async def redeem_voucher_admin(session: DbSession, body: RedeemBody, admin: User = Depends(get_current_user)):
    """Admin/manual redemption; same core flow as portal (locking, grant, audit)."""
    payload = await redeem_voucher(
        session,
        site_id=body.site_id,
        code=body.code,
        pin=body.pin,
        customer_id=body.customer_id,
        actor_user_id=admin.id,
        channel="admin",
        enforce_site_plan=body.site_id is not None,
    )
    return ok(payload, message="Redeemed")
