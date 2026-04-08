"""Machine-readable permission codes — map to rows in ``permissions`` table."""

# Auth / users
PERM_USERS_READ = "users:read"
PERM_USERS_WRITE = "users:write"

# RBAC admin
PERM_ROLES_READ = "roles:read"
PERM_ROLES_WRITE = "roles:write"

# Infrastructure
PERM_SITES_READ = "sites:read"
PERM_SITES_WRITE = "sites:write"
PERM_ROUTERS_READ = "routers:read"
PERM_ROUTERS_WRITE = "routers:write"
PERM_ROUTERS_SYNC = "routers:sync"
PERM_SESSIONS_READ = "sessions:read"
PERM_SESSIONS_TERMINATE = "sessions:terminate"
PERM_DEVICES_BLOCK = "devices:block"

# Business
PERM_CUSTOMERS_READ = "customers:read"
PERM_CUSTOMERS_WRITE = "customers:write"
PERM_PLANS_READ = "plans:read"
PERM_PLANS_WRITE = "plans:write"
PERM_VOUCHERS_READ = "vouchers:read"
PERM_VOUCHERS_WRITE = "vouchers:write"
PERM_PAYMENTS_READ = "payments:read"
PERM_PAYMENTS_WRITE = "payments:write"
PERM_PAYMENTS_CALLBACK = "payments:callback"
PERM_ANALYTICS_READ = "analytics:read"
PERM_NOTIFICATIONS_READ = "notifications:read"
PERM_SETTINGS_READ = "settings:read"
PERM_SETTINGS_WRITE = "settings:write"
PERM_AUDIT_READ = "audit:read"

ALL_PERMISSION_CODES: tuple[str, ...] = (
    PERM_USERS_READ,
    PERM_USERS_WRITE,
    PERM_ROLES_READ,
    PERM_ROLES_WRITE,
    PERM_SITES_READ,
    PERM_SITES_WRITE,
    PERM_ROUTERS_READ,
    PERM_ROUTERS_WRITE,
    PERM_ROUTERS_SYNC,
    PERM_SESSIONS_READ,
    PERM_SESSIONS_TERMINATE,
    PERM_DEVICES_BLOCK,
    PERM_CUSTOMERS_READ,
    PERM_CUSTOMERS_WRITE,
    PERM_PLANS_READ,
    PERM_PLANS_WRITE,
    PERM_VOUCHERS_READ,
    PERM_VOUCHERS_WRITE,
    PERM_PAYMENTS_READ,
    PERM_PAYMENTS_WRITE,
    PERM_PAYMENTS_CALLBACK,
    PERM_ANALYTICS_READ,
    PERM_NOTIFICATIONS_READ,
    PERM_SETTINGS_READ,
    PERM_SETTINGS_WRITE,
    PERM_AUDIT_READ,
)
