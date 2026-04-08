"""Import all ORM models so Base.metadata is complete for Alembic."""

from app.modules.auth.models import User  # noqa: F401
from app.modules.access_control.models import AuditLog, Permission, Role, RolePermission, UserRole  # noqa: F401
from app.modules.customers.models import Customer, CustomerDevice, CustomerNote  # noqa: F401
from app.modules.notifications.models import Notification, NotificationDelivery  # noqa: F401
from app.modules.payments.models import Payment, PaymentCallback, PaymentEvent  # noqa: F401
from app.modules.plans.models import Plan, PlanRouterAvailability  # noqa: F401
from app.modules.portal.models import PortalBranding  # noqa: F401
from app.modules.routers.models import Router, RouterStatusSnapshot, RouterSyncLog, Site  # noqa: F401
from app.modules.settings.models import SystemSetting  # noqa: F401
from app.modules.sessions.models import BlockedDevice, HotspotSession, HotspotSessionUsage, WhitelistedDevice  # noqa: F401
from app.modules.subscriptions.models import CustomerAccessGrant  # noqa: F401
from app.modules.vouchers.models import Voucher, VoucherBatch  # noqa: F401
