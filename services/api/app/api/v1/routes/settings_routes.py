from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.responses import ok
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_SETTINGS_READ, PERM_SETTINGS_WRITE
from app.modules.auth.models import User
from app.modules.settings.models import SystemSetting

router = APIRouter()


class SettingUpsert(BaseModel):
    key: str
    value: dict[str, Any] | None = None
    description: str | None = None


@router.get("/settings", dependencies=[Depends(require_permissions(PERM_SETTINGS_READ))])
async def list_settings(session: DbSession, _u: User = Depends(get_current_user)):
    rows = (await session.execute(select(SystemSetting).order_by(SystemSetting.key))).scalars().all()
    return ok([{"key": r.key, "value": r.value, "description": r.description} for r in rows])


@router.put("/settings", dependencies=[Depends(require_permissions(PERM_SETTINGS_WRITE))])
async def upsert_setting(session: DbSession, body: SettingUpsert, admin: User = Depends(get_current_user)):
    row = (await session.execute(select(SystemSetting).where(SystemSetting.key == body.key))).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=body.key, value=body.value, description=body.description)
        session.add(row)
    else:
        row.value = body.value if body.value is not None else row.value
        if body.description is not None:
            row.description = body.description
    await session.flush()
    await record_audit(session, user_id=admin.id, action="settings.upsert", resource_type="setting", resource_id=body.key)
    return ok(message="Setting saved")
