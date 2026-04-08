from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.responses import ok, ok_paginated
from app.modules.access_control.audit_query import list_audit_logs_filtered
from app.modules.access_control.constants import PERM_AUDIT_READ
from app.modules.auth.models import User

router = APIRouter()


@router.get("/audit-logs", dependencies=[Depends(require_permissions(PERM_AUDIT_READ))])
async def list_audit_logs(
    session: DbSession,
    _u: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    actor_user_id: uuid.UUID | None = None,
    module: str | None = Query(None, description="resource_type, e.g. router, payment"),
    action: str | None = Query(None, description="action prefix filter, e.g. router."),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    rows, total = await list_audit_logs_filtered(
        session,
        user_id=actor_user_id,
        resource_type=module,
        action_prefix=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    data = [
        {
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "user_id": str(r.user_id) if r.user_id else None,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "details": r.details,
            "ip_address": r.ip_address,
        }
        for r in rows
    ]
    return ok_paginated(data, page=page, per_page=per_page, total=total, message="OK")
