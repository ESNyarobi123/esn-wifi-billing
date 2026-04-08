"""Portal request bodies shared by HTTP routes and rate-limit dependencies."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class PortalPayBody(BaseModel):
    plan_id: uuid.UUID
    amount: Decimal
    currency: str = Field(default="TZS", max_length=8)
    customer_id: uuid.UUID | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    full_name: str | None = Field(default=None, max_length=200)
    hotspot_context: dict[str, str | None] | None = None


class PortalRedeemBody(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    pin: str | None = Field(default=None, max_length=32)
    customer_id: uuid.UUID | None = Field(default=None, description="Customer uuid receiving hotspot access.")
    hotspot_context: dict[str, str | None] | None = None


class PortalSessionQuery(BaseModel):
    mac_address: str = Field(min_length=5, max_length=32)
