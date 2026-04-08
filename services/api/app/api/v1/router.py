from fastapi import APIRouter

from app.api.v1.routes import (
    analytics,
    audit,
    auth,
    customers,
    health,
    notifications,
    payments,
    permissions,
    plans,
    portal,
    roles,
    router_mgmt,
    sessions_mgmt,
    settings_routes,
    sites,
    users,
    vouchers,
)

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, tags=["users"])
router.include_router(roles.router, tags=["roles"])
router.include_router(permissions.router, tags=["permissions"])
router.include_router(sites.router, tags=["sites"])
router.include_router(router_mgmt.router, tags=["routers"])
router.include_router(customers.router, tags=["customers"])
router.include_router(sessions_mgmt.router, tags=["sessions"])
router.include_router(plans.router, tags=["plans"])
router.include_router(vouchers.router, tags=["vouchers"])
router.include_router(payments.router, tags=["payments"])
router.include_router(analytics.router, tags=["analytics"])
router.include_router(notifications.router, tags=["notifications"])
router.include_router(portal.router, tags=["portal"])
router.include_router(settings_routes.router, tags=["settings"])
router.include_router(audit.router, tags=["audit"])
