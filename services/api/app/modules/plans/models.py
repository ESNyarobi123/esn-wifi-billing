from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.routers.models import Router


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, Base):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_type: Mapped[str] = mapped_column(String(32), index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_bytes_quota: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bandwidth_up_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bandwidth_down_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="TZS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    router_links: Mapped[list[PlanRouterAvailability]] = relationship(
        "PlanRouterAvailability",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class PlanRouterAvailability(Base):
    __tablename__ = "plan_router_availability"
    __table_args__ = (UniqueConstraint("plan_id", "router_id", name="uq_plan_router"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    router_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routers.id", ondelete="CASCADE"),
        primary_key=True,
    )

    plan: Mapped[Plan] = relationship("Plan", back_populates="router_links")
    router: Mapped[Router] = relationship("Router")
