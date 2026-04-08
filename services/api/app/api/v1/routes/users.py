from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import ConflictError
from app.core.exceptions import NotFoundError
from app.core.responses import dump_model, ok, ok_paginated
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_USERS_READ, PERM_USERS_WRITE
from app.modules.access_control.models import UserRole
from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate, UserPublic
from app.modules.auth.service import create_user

router = APIRouter()


class AssignRoleBody(BaseModel):
    role_id: uuid.UUID


@router.get("/users", dependencies=[Depends(require_permissions(PERM_USERS_READ))])
async def list_users(session: DbSession, user: User = Depends(get_current_user), page: int = 1, per_page: int = 20):
    _ = user
    stmt = select(User).order_by(User.created_at.desc())
    count_stmt = select(func.count()).select_from(User)
    offset = (page - 1) * per_page
    total = int((await session.execute(count_stmt)).scalar_one())
    rows = (await session.execute(stmt.offset(offset).limit(per_page))).scalars().all()
    return ok_paginated([dump_model(UserPublic.model_validate(u)) for u in rows], page=page, per_page=per_page, total=total)


@router.post("/users", dependencies=[Depends(require_permissions(PERM_USERS_WRITE))])
async def create_user_admin(session: DbSession, body: UserCreate, user: User = Depends(get_current_user)):
    _ = user
    u = await create_user(session, body)
    return ok(dump_model(UserPublic.model_validate(u)), message="User created")


@router.post("/users/{user_id}/roles", dependencies=[Depends(require_permissions(PERM_USERS_WRITE))])
async def assign_role(session: DbSession, user_id: uuid.UUID, body: AssignRoleBody, admin: User = Depends(get_current_user)):
    exists = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if exists is None:
        raise NotFoundError("User not found")
    try:
        session.add(UserRole(user_id=user_id, role_id=body.role_id))
        await session.flush()
    except IntegrityError as e:
        raise ConflictError("Role already assigned") from e
    await record_audit(
        session,
        user_id=admin.id,
        action="user.role_assign",
        resource_type="user",
        resource_id=str(user_id),
        details={"role_id": str(body.role_id)},
    )
    return ok(message="Role assigned")


@router.delete("/users/{user_id}/roles/{role_id}", dependencies=[Depends(require_permissions(PERM_USERS_WRITE))])
async def remove_role(session: DbSession, user_id: uuid.UUID, role_id: uuid.UUID, admin: User = Depends(get_current_user)):
    res = await session.execute(delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id))
    if res.rowcount == 0:
        raise NotFoundError("Role assignment not found")
    await record_audit(
        session,
        user_id=admin.id,
        action="user.role_remove",
        resource_type="user",
        resource_id=str(user_id),
        details={"role_id": str(role_id)},
    )
    return ok(message="Role removed")
