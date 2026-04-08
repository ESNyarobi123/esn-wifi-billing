from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.responses import ok
from app.modules.access_control.constants import PERM_ROLES_READ
from app.modules.access_control.models import Permission
from app.modules.auth.models import User

router = APIRouter()


@router.get("/permissions", dependencies=[Depends(require_permissions(PERM_ROLES_READ))])
async def list_permissions(session: DbSession, _user: User = Depends(get_current_user)):
    rows = (await session.execute(select(Permission).order_by(Permission.code))).scalars().all()
    return ok([{"id": str(p.id), "code": p.code, "description": p.description} for p in rows])
