from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError
from app.core.responses import ok
from app.modules.access_control.constants import PERM_NOTIFICATIONS_READ
from app.modules.auth.models import User
from app.modules.notifications.models import Notification

router = APIRouter()


@router.get("/notifications", dependencies=[Depends(require_permissions(PERM_NOTIFICATIONS_READ))])
async def list_notifications(session: DbSession, user: User = Depends(get_current_user), limit: int = 50):
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit),
        )
    ).scalars().all()
    return ok(
        [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
    )


@router.post("/notifications/{notification_id}/read", dependencies=[Depends(require_permissions(PERM_NOTIFICATIONS_READ))])
async def mark_read(session: DbSession, notification_id: uuid.UUID, user: User = Depends(get_current_user)):
    n = (
        await session.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id),
        )
    ).scalar_one_or_none()
    if n is None:
        raise NotFoundError("Notification not found")
    n.read_at = datetime.now(UTC)
    return ok(message="Marked read")
