from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin


class VoucherBatch(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, Base):
    __tablename__ = "voucher_batches"

    name: Mapped[str] = mapped_column(String(255))
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column()
    prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    requires_pin: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    vouchers: Mapped[list[Voucher]] = relationship("Voucher", back_populates="batch")


class Voucher(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, Base):
    __tablename__ = "vouchers"

    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voucher_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    batch: Mapped[VoucherBatch | None] = relationship("VoucherBatch", back_populates="vouchers")
