"""Bootstrap RBAC and optional demo dataset.

Run from ``services/api`` with ``PYTHONPATH`` set to the api root::

    python -m app.seed

- **Default:** ``SEED_DEMO_DATA=false`` (or unset) — only permissions, roles, admin/support users,
  one empty **site** ``hq`` with portal branding shell and default portal settings. Add routers,
  plans, and customers via the admin UI (real data).
- **Demo workshop:** set ``SEED_DEMO_DATA=true`` to also load sample plans, customers, vouchers,
  payments, and (if ``ROUTER_CREDENTIALS_FERNET_KEY`` is set) a demo router row.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.security import encrypt_secret, hash_password
from app.db.enums import AccessGrantSource, AccessGrantStatus, PaymentStatus, PlanType, SessionStatus, VoucherStatus
from app.db.session import async_session_factory
from app.modules.access_control.constants import (
    ALL_PERMISSION_CODES,
    PERM_ANALYTICS_READ,
    PERM_CUSTOMERS_READ,
    PERM_NOTIFICATIONS_READ,
    PERM_PAYMENTS_READ,
    PERM_PLANS_READ,
    PERM_ROUTERS_READ,
    PERM_SESSIONS_READ,
    PERM_SITES_READ,
    PERM_VOUCHERS_READ,
)
from app.modules.access_control.models import Permission, Role, RolePermission, UserRole
from app.modules.auth.models import User
from app.modules.customers.models import Customer, CustomerDevice
from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment, PaymentEvent
from app.modules.plans.models import Plan, PlanRouterAvailability
from app.modules.portal.models import PortalBranding
from app.modules.routers.models import Router, Site
from app.modules.settings.models import SystemSetting
from app.modules.subscriptions.models import CustomerAccessGrant
from app.modules.sessions.models import HotspotSession
from app.modules.vouchers.models import Voucher, VoucherBatch


def _seed_demo_data() -> bool:
    return os.environ.get("SEED_DEMO_DATA", "false").strip().lower() in ("1", "true", "yes", "on")


async def _run() -> None:
    async with async_session_factory() as session:
        existing_codes = set((await session.execute(select(Permission.code))).scalars().all())
        for code in ALL_PERMISSION_CODES:
            if code in existing_codes:
                continue
            session.add(Permission(code=code, description=code))
        await session.flush()

        admin_role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one_or_none()
        if admin_role is None:
            admin_role = Role(name="admin", description="Full access")
            session.add(admin_role)
            await session.flush()

        all_perms = (await session.execute(select(Permission))).scalars().all()
        assigned = {
            rp.permission_id
            for rp in (
                await session.execute(select(RolePermission).where(RolePermission.role_id == admin_role.id))
            ).scalars().all()
        }
        for p in all_perms:
            if p.id not in assigned:
                session.add(RolePermission(role_id=admin_role.id, permission_id=p.id))

        support_role = (await session.execute(select(Role).where(Role.name == "support"))).scalar_one_or_none()
        if support_role is None:
            support_role = Role(name="support", description="Support desk (read-heavy)")
            session.add(support_role)
            await session.flush()
        support_codes = frozenset(
            {
                PERM_CUSTOMERS_READ,
                PERM_PLANS_READ,
                PERM_VOUCHERS_READ,
                PERM_ROUTERS_READ,
                PERM_SITES_READ,
                PERM_SESSIONS_READ,
                PERM_PAYMENTS_READ,
                PERM_NOTIFICATIONS_READ,
                PERM_ANALYTICS_READ,
            },
        )
        support_assigned = {
            rp.permission_id
            for rp in (
                await session.execute(select(RolePermission).where(RolePermission.role_id == support_role.id))
            ).scalars().all()
        }
        for p in all_perms:
            if p.code in support_codes and p.id not in support_assigned:
                session.add(RolePermission(role_id=support_role.id, permission_id=p.id))

        user = (await session.execute(select(User).where(User.email == "admin@esn.local"))).scalar_one_or_none()
        if user is None:
            user = User(
                email="admin@esn.local",
                password_hash=hash_password(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")),
                full_name="ESN Admin",
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=admin_role.id))

        support_user = (await session.execute(select(User).where(User.email == "support@esn.local"))).scalar_one_or_none()
        if support_user is None:
            support_user = User(
                email="support@esn.local",
                password_hash=hash_password(os.environ.get("SEED_SUPPORT_PASSWORD", "Support123!")),
                full_name="Support Operator",
            )
            session.add(support_user)
            await session.flush()
            session.add(UserRole(user_id=support_user.id, role_id=support_role.id))

        site = (await session.execute(select(Site).where(Site.slug == "hq"))).scalar_one_or_none()
        if site is None:
            site = Site(name="Headquarters", slug="hq", address="Dar es Salaam")
            session.add(site)
            await session.flush()

        if (await session.execute(select(PortalBranding).where(PortalBranding.site_id == site.id))).scalar_one_or_none() is None:
            session.add(
                PortalBranding(
                    site_id=site.id,
                    welcome_message="Welcome to ESN WiFi",
                    primary_color="#0ea5e9",
                    support_phone="+255700000000",
                ),
            )

        if (await session.execute(select(SystemSetting).where(SystemSetting.key == "company_name"))).scalar_one_or_none() is None:
            session.add(SystemSetting(key="company_name", value={"name": "ESN WiFi"}, description="Portal company"))
        if (await session.execute(select(SystemSetting).where(SystemSetting.key == "support_email"))).scalar_one_or_none() is None:
            session.add(
                SystemSetting(
                    key="support_email",
                    value={"email": "support@esn.local"},
                    description="Public portal support email",
                ),
            )

        if not _seed_demo_data():
            await session.commit()
            print(
                "Minimal seed complete (SEED_DEMO_DATA off). RBAC + site `hq` only; dashboard and lists use live DB data you create.\n"
                "  Admin:    admin@esn.local / (SEED_ADMIN_PASSWORD or ChangeMe123!)\n"
                "  Support:  support@esn.local / (SEED_SUPPORT_PASSWORD or Support123!)\n"
                "  Full demo dataset: SEED_DEMO_DATA=true python -m app.seed",
            )
            return

        plan = (await session.execute(select(Plan).where(Plan.name == "1 Hour"))).scalar_one_or_none()
        if plan is None:
            plan = Plan(
                name="1 Hour",
                description="Hotspot 1 hour",
                plan_type=PlanType.time.value,
                duration_seconds=3600,
                price_amount=Decimal("1000.00"),
                currency="TZS",
            )
            session.add(plan)
            await session.flush()

        demo_plans_specs = [
            ("Evening Pass", "4 hours peak time", PlanType.time.value, 4 * 3600, Decimal("2500.00")),
            ("Full Day", "24h uninterrupted", PlanType.time.value, 86400, Decimal("5000.00")),
            ("Weekend Pack", "48h bundle", PlanType.time.value, 2 * 86400, Decimal("9000.00")),
            ("Lite 15m", "Quick browse", PlanType.time.value, 900, Decimal("500.00")),
        ]
        for name, desc, ptype, dur, price in demo_plans_specs:
            if (await session.execute(select(Plan).where(Plan.name == name))).scalar_one_or_none() is None:
                session.add(
                    Plan(
                        name=name,
                        description=desc,
                        plan_type=ptype,
                        duration_seconds=dur,
                        price_amount=price,
                        currency="TZS",
                    ),
                )
        await session.flush()

        router: Router | None = (await session.execute(select(Router).where(Router.name == "demo-router"))).scalar_one_or_none()
        if router is None and settings.router_credentials_fernet_key:
            enc = encrypt_secret(os.environ.get("SEED_ROUTER_PASSWORD", "router-password"))
            router = Router(
                site_id=site.id,
                name="demo-router",
                host="192.0.2.1",
                api_port=8728,
                username="admin",
                password_encrypted=enc,
                use_tls=False,
                is_online=False,
            )
            session.add(router)
            await session.flush()
        elif router is None:
            print("Skipping demo router — set ROUTER_CREDENTIALS_FERNET_KEY to seed encrypted credentials.")

        if router is not None:
            links = {plan.id}
            for _n, _d, _t, _dur, _p in demo_plans_specs:
                op = (await session.execute(select(Plan).where(Plan.name == _n))).scalar_one_or_none()
                if op:
                    links.add(op.id)
            for pid in links:
                exists_l = (
                    await session.execute(
                        select(PlanRouterAvailability).where(
                            PlanRouterAvailability.plan_id == pid,
                            PlanRouterAvailability.router_id == router.id,
                        ),
                    )
                ).scalar_one_or_none()
                if exists_l is None:
                    session.add(PlanRouterAvailability(plan_id=pid, router_id=router.id))
            await session.flush()

        customer = (await session.execute(select(Customer).where(Customer.email == "customer@example.com"))).scalar_one_or_none()
        if customer is None:
            customer = Customer(site_id=site.id, email="customer@example.com", full_name="Demo Customer")
            session.add(customer)
            await session.flush()

        if (
            await session.execute(select(CustomerDevice).where(CustomerDevice.mac_address == "11:22:33:44:55:66"))
        ).scalar_one_or_none() is None:
            session.add(
                CustomerDevice(
                    customer_id=customer.id,
                    site_id=site.id,
                    mac_address="11:22:33:44:55:66",
                    hostname="demo-laptop",
                    first_seen_at=datetime.now(UTC),
                ),
            )

        batch = (await session.execute(select(VoucherBatch).where(VoucherBatch.name == "demo-batch"))).scalar_one_or_none()
        if batch is None:
            batch = VoucherBatch(name="demo-batch", plan_id=plan.id, quantity=3, prefix="ESN")
            session.add(batch)
            await session.flush()
            for i in range(3):
                session.add(
                    Voucher(
                        batch_id=batch.id,
                        plan_id=plan.id,
                        code=f"ESN-DEMO-{i+1}",
                        status=VoucherStatus.unused.value,
                        expires_at=datetime.now(UTC) + timedelta(days=30),
                    ),
                )

        seed_payment = (await session.execute(select(Payment).where(Payment.order_reference == "SEED-ORDER-1"))).scalar_one_or_none()
        if seed_payment is None:
            seed_payment = Payment(
                provider="mock",
                order_reference="SEED-ORDER-1",
                amount=1000.0,
                currency="TZS",
                payment_status=PaymentStatus.success.value,
                customer_id=customer.id,
                plan_id=plan.id,
                site_id=site.id,
            )
            session.add(seed_payment)
            await session.flush()
        if (
            await session.execute(
                select(PaymentEvent).where(PaymentEvent.payment_id == seed_payment.id, PaymentEvent.event_type == "seed_demo"),
            )
        ).scalar_one_or_none() is None:
            session.add(
                PaymentEvent(
                    payment_id=seed_payment.id,
                    event_type="seed_demo",
                    payload={"note": "Demo payment timeline event"},
                ),
            )

        if (
            await session.execute(select(CustomerAccessGrant).where(CustomerAccessGrant.payment_id == seed_payment.id))
        ).scalar_one_or_none() is None:
            session.add(
                CustomerAccessGrant(
                    customer_id=customer.id,
                    site_id=site.id,
                    plan_id=plan.id,
                    payment_id=seed_payment.id,
                    source=AccessGrantSource.payment.value,
                    status=AccessGrantStatus.active.value,
                    starts_at=datetime.now(UTC) - timedelta(minutes=30),
                    ends_at=datetime.now(UTC) + timedelta(seconds=int(plan.duration_seconds or 3600) - 1800),
                ),
            )

        if (await session.execute(select(Payment).where(Payment.order_reference == "SEED-PENDING-1"))).scalar_one_or_none() is None:
            session.add(
                Payment(
                    provider="mock",
                    order_reference="SEED-PENDING-1",
                    amount=float(plan.price_amount),
                    currency="TZS",
                    payment_status=PaymentStatus.pending.value,
                    customer_id=customer.id,
                    plan_id=plan.id,
                    site_id=site.id,
                ),
            )

        cust_active = (await session.execute(select(Customer).where(Customer.email == "active@demo.esn"))).scalar_one_or_none()
        if cust_active is None:
            cust_active = Customer(site_id=site.id, email="active@demo.esn", full_name="Active Access Customer")
            session.add(cust_active)
            await session.flush()
        if (
            await session.execute(
                select(CustomerAccessGrant).where(
                    CustomerAccessGrant.customer_id == cust_active.id,
                    CustomerAccessGrant.source == AccessGrantSource.manual.value,
                ),
            )
        ).scalar_one_or_none() is None:
            session.add(
                CustomerAccessGrant(
                    customer_id=cust_active.id,
                    site_id=site.id,
                    plan_id=plan.id,
                    voucher_id=None,
                    payment_id=None,
                    source=AccessGrantSource.manual.value,
                    status=AccessGrantStatus.active.value,
                    starts_at=datetime.now(UTC) - timedelta(hours=1),
                    ends_at=datetime.now(UTC) + timedelta(hours=5),
                ),
            )

        cust_exp = (await session.execute(select(Customer).where(Customer.email == "expired@demo.esn"))).scalar_one_or_none()
        if cust_exp is None:
            cust_exp = Customer(site_id=site.id, email="expired@demo.esn", full_name="Expired Access Customer")
            session.add(cust_exp)
            await session.flush()
        if (
            await session.execute(
                select(CustomerAccessGrant).where(
                    CustomerAccessGrant.customer_id == cust_exp.id,
                    CustomerAccessGrant.source == AccessGrantSource.manual.value,
                ),
            )
        ).scalar_one_or_none() is None:
            session.add(
                CustomerAccessGrant(
                    customer_id=cust_exp.id,
                    site_id=site.id,
                    plan_id=plan.id,
                    voucher_id=None,
                    payment_id=None,
                    source=AccessGrantSource.manual.value,
                    status=AccessGrantStatus.expired.value,
                    starts_at=datetime.now(UTC) - timedelta(days=3),
                    ends_at=datetime.now(UTC) - timedelta(days=1),
                ),
            )

        demo_voucher_specs = [
            ("SEED-REDEEM-OK", VoucherStatus.unused.value, datetime.now(UTC) + timedelta(days=60), None),
            ("SEED-REDEEM-USED", VoucherStatus.used.value, datetime.now(UTC) + timedelta(days=60), customer.id),
            ("SEED-REDEEM-EXP", VoucherStatus.unused.value, datetime.now(UTC) - timedelta(days=1), None),
        ]
        for code, st, exp_at, assign in demo_voucher_specs:
            if (await session.execute(select(Voucher).where(Voucher.code == code))).scalar_one_or_none() is None:
                session.add(
                    Voucher(
                        plan_id=plan.id,
                        code=code,
                        status=st,
                        expires_at=exp_at,
                        assigned_customer_id=assign,
                    ),
                )

        if (await session.execute(select(Notification).where(Notification.title == "Welcome"))).scalar_one_or_none() is None:
            session.add(
                Notification(
                    user_id=user.id,
                    type="system",
                    title="Welcome",
                    body="Seeded notification",
                    status="active",
                ),
            )

        if (
            await session.execute(
                select(Notification).where(
                    Notification.customer_id == customer.id,
                    Notification.type == "payment_success",
                    Notification.title == "Demo customer alert",
                ),
            )
        ).scalar_one_or_none() is None:
            session.add(
                Notification(
                    customer_id=customer.id,
                    type="payment_success",
                    title="Demo customer alert",
                    body="Sample payment notification for the demo customer.",
                    status="active",
                    data={"demo": True},
                ),
            )

        if router is not None:
            if (
                await session.execute(select(HotspotSession).where(HotspotSession.mac_address == "AA:BB:CC:DD:EE:FF"))
            ).scalar_one_or_none() is None:
                session.add(
                    HotspotSession(
                        router_id=router.id,
                        customer_id=customer.id,
                        plan_id=plan.id,
                        mac_address="AA:BB:CC:DD:EE:FF",
                        username="demo",
                        login_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        status=SessionStatus.active.value,
                    ),
                )

        await session.commit()
        print(
            "Demo seed complete (SEED_DEMO_DATA=true).\n"
            "  Admin:    admin@esn.local / (SEED_ADMIN_PASSWORD or ChangeMe123!)\n"
            "  Support:  support@esn.local / (SEED_SUPPORT_PASSWORD or Support123!)",
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
