from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import AccountStatus
from app.db.mixins import StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, Base):
    __tablename__ = "customers"

    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    account_status: Mapped[str] = mapped_column(String(32), default=AccountStatus.active.value, index=True)

    devices: Mapped[list[CustomerDevice]] = relationship(
        "CustomerDevice",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list[CustomerNote]] = relationship(
        "CustomerNote",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class CustomerDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_devices"
    __table_args__ = (UniqueConstraint("site_id", "mac_address", name="uq_site_mac"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mac_address: Mapped[str] = mapped_column(String(32), index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[Customer] = relationship("Customer", back_populates="devices")


class CustomerNote(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "customer_notes"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped[Customer] = relationship("Customer", back_populates="notes")
    created_by: Mapped[User | None] = relationship("User")
