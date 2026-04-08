from __future__ import annotations

import enum


class RecordStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    deleted = "deleted"


class AccountStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    closed = "closed"


class PlanType(str, enum.Enum):
    time = "time"
    data = "data"
    unlimited = "unlimited"


class VoucherStatus(str, enum.Enum):
    unused = "unused"
    active = "active"
    used = "used"
    expired = "expired"
    disabled = "disabled"


class SessionStatus(str, enum.Enum):
    active = "active"
    terminated = "terminated"
    expired = "expired"
    suspicious = "suspicious"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class AccessGrantStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    expired = "expired"
    revoked = "revoked"
    consumed = "consumed"
    cancelled = "cancelled"


class AccessGrantSource(str, enum.Enum):
    payment = "payment"
    voucher = "voucher"
    manual = "manual"
