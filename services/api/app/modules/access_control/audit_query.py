from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access_control.models import AuditLog


async def list_audit_logs_filtered(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    action_prefix: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    count_base = select(func.count()).select_from(AuditLog)

    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_base = count_base.where(AuditLog.user_id == user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_base = count_base.where(AuditLog.resource_type == resource_type)
    if action_prefix:
        stmt = stmt.where(AuditLog.action.startswith(action_prefix))
        count_base = count_base.where(AuditLog.action.startswith(action_prefix))
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
        count_base = count_base.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
        count_base = count_base.where(AuditLog.created_at <= date_to)

    total = int((await session.execute(count_base)).scalar_one())
    offset = (page - 1) * per_page
    stmt = stmt.order_by(desc(AuditLog.created_at), desc(AuditLog.id)).offset(offset).limit(per_page)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total
