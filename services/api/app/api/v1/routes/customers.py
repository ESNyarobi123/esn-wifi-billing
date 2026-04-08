from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError
from app.core.responses import ok
from app.modules.access_control.constants import PERM_CUSTOMERS_READ, PERM_CUSTOMERS_WRITE
from app.modules.auth.models import User
from app.modules.customers.models import Customer, CustomerDevice
from app.modules.payments.models import Payment
from app.modules.subscriptions import service as subs_service
from app.modules.sessions.models import HotspotSession
from app.modules.vouchers.models import Voucher

router = APIRouter()


class CustomerCreate(BaseModel):
    site_id: uuid.UUID | None = None
    email: EmailStr | None = None
    phone: str | None = None
    full_name: str = ""


class DeviceAttach(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    mac_address: str = Field(min_length=5, max_length=32)
    hostname: str | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    site_id: uuid.UUID | None = None
    account_status: str | None = None


@router.get("/customers", dependencies=[Depends(require_permissions(PERM_CUSTOMERS_READ))])
async def list_customers(session: DbSession, _u: User = Depends(get_current_user)):
    rows = (await session.execute(select(Customer).order_by(Customer.created_at.desc()))).scalars().all()
    return ok(
        [
            {
                "id": str(c.id),
                "full_name": c.full_name,
                "email": c.email,
                "phone": c.phone,
                "account_status": c.account_status,
                "site_id": str(c.site_id) if c.site_id else None,
            }
            for c in rows
        ],
    )


@router.post("/customers", dependencies=[Depends(require_permissions(PERM_CUSTOMERS_WRITE))])
async def create_customer(session: DbSession, body: CustomerCreate, _u: User = Depends(get_current_user)):
    c = Customer(
        site_id=body.site_id,
        email=body.email,
        phone=body.phone,
        full_name=body.full_name,
    )
    session.add(c)
    await session.flush()
    return ok({"id": str(c.id)}, message="Customer created")


@router.get("/customers/{customer_id}", dependencies=[Depends(require_permissions(PERM_CUSTOMERS_READ))])
async def get_customer(session: DbSession, customer_id: uuid.UUID, _u: User = Depends(get_current_user)):
    c = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if c is None:
        raise NotFoundError("Customer not found")
    devices = (
        await session.execute(select(CustomerDevice).where(CustomerDevice.customer_id == customer_id))
    ).scalars().all()
    payments = (
        await session.execute(
            select(Payment).where(Payment.customer_id == customer_id).order_by(Payment.created_at.desc()).limit(50),
        )
    ).scalars().all()
    vouchers = (
        await session.execute(
            select(Voucher)
            .where(Voucher.assigned_customer_id == customer_id)
            .order_by(Voucher.created_at.desc())
            .limit(50),
        )
    ).scalars().all()
    sessions = (
        await session.execute(
            select(HotspotSession)
            .where(HotspotSession.customer_id == customer_id)
            .order_by(HotspotSession.login_at.desc())
            .limit(50),
        )
    ).scalars().all()
    access_grants = await subs_service.serialize_access_grants_for_customer(session, customer_id, limit=50)
    return ok(
        {
            "id": str(c.id),
            "full_name": c.full_name,
            "email": c.email,
            "phone": c.phone,
            "account_status": c.account_status,
            "site_id": str(c.site_id) if c.site_id else None,
            "devices": [
                {"id": str(d.id), "mac_address": d.mac_address, "hostname": d.hostname} for d in devices
            ],
            "payments": [
                {
                    "id": str(pay.id),
                    "order_reference": pay.order_reference,
                    "amount": str(pay.amount),
                    "currency": pay.currency,
                    "payment_status": pay.payment_status,
                    "created_at": pay.created_at.isoformat(),
                }
                for pay in payments
            ],
            "access_grants": access_grants,
            "vouchers": [
                {
                    "id": str(v.id),
                    "code": v.code,
                    "status": v.status,
                    "plan_id": str(v.plan_id),
                }
                for v in vouchers
            ],
            "session_history": [
                {
                    "id": str(s.id),
                    "router_id": str(s.router_id),
                    "mac_address": s.mac_address,
                    "login_at": s.login_at.isoformat(),
                    "status": s.status,
                    "bytes_up": s.bytes_up,
                    "bytes_down": s.bytes_down,
                }
                for s in sessions
            ],
        },
    )


@router.get(
    "/customers/{customer_id}/access-grants",
    dependencies=[Depends(require_permissions(PERM_CUSTOMERS_READ))],
)
async def list_customer_access_grants(
    session: DbSession,
    customer_id: uuid.UUID,
    _u: User = Depends(get_current_user),
    limit: int = 50,
):
    c = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if c is None:
        raise NotFoundError("Customer not found")
    rows = await subs_service.serialize_access_grants_for_customer(session, customer_id, limit=limit)
    return ok(rows)


@router.patch("/customers/{customer_id}", dependencies=[Depends(require_permissions(PERM_CUSTOMERS_WRITE))])
async def update_customer(
    session: DbSession,
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    _u: User = Depends(get_current_user),
):
    c = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if c is None:
        raise NotFoundError("Customer not found")
    if body.full_name is not None:
        c.full_name = body.full_name
    if body.email is not None:
        c.email = body.email
    if body.phone is not None:
        c.phone = body.phone
    if body.site_id is not None:
        c.site_id = body.site_id
    if body.account_status is not None:
        c.account_status = body.account_status
    return ok(message="Customer updated")


@router.post("/customer-devices", dependencies=[Depends(require_permissions(PERM_CUSTOMERS_WRITE))])
async def attach_device(session: DbSession, body: DeviceAttach, _u: User = Depends(get_current_user)):
    cust = (await session.execute(select(Customer).where(Customer.id == body.customer_id))).scalar_one_or_none()
    if cust is None:
        raise NotFoundError("Customer not found")
    d = CustomerDevice(
        customer_id=body.customer_id,
        site_id=body.site_id,
        mac_address=body.mac_address.upper().replace("-", ":"),
        hostname=body.hostname,
        first_seen_at=datetime.now(UTC),
    )
    session.add(d)
    await session.flush()
    return ok({"id": str(d.id)}, message="Device attached")


@router.delete("/customer-devices/{device_id}", dependencies=[Depends(require_permissions(PERM_CUSTOMERS_WRITE))])
async def remove_device(session: DbSession, device_id: uuid.UUID, _u: User = Depends(get_current_user)):
    res = await session.execute(delete(CustomerDevice).where(CustomerDevice.id == device_id))
    if res.rowcount == 0:
        raise NotFoundError("Device not found")
    return ok(message="Device removed")
