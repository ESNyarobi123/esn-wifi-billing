from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import ConflictError, NotFoundError
from app.core.responses import ok
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_ROLES_READ, PERM_ROLES_WRITE
from app.modules.access_control.models import Role, RolePermission, UserRole
from app.modules.auth.models import User

router = APIRouter()


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str = ""


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    description: str | None = None


def _serialize_role(r: Role) -> dict:
    codes = [rp.permission.code for rp in r.permissions]
    return {"id": str(r.id), "name": r.name, "description": r.description, "permissions": codes}


class RolePermissionsBody(BaseModel):
    permission_ids: list[uuid.UUID]


@router.get("/roles", dependencies=[Depends(require_permissions(PERM_ROLES_READ))])
async def list_roles(session: DbSession, _u: User = Depends(get_current_user)):
    rows = (
        await session.execute(
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .order_by(Role.name),
        )
    ).scalars().all()
    return ok([_serialize_role(r) for r in rows])


@router.get("/roles/{role_id}", dependencies=[Depends(require_permissions(PERM_ROLES_READ))])
async def get_role(session: DbSession, role_id: uuid.UUID, _u: User = Depends(get_current_user)):
    r = (
        await session.execute(
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role_id),
        )
    ).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Role not found")
    return ok(_serialize_role(r))


@router.post("/roles", dependencies=[Depends(require_permissions(PERM_ROLES_WRITE))])
async def create_role(session: DbSession, body: RoleCreate, admin: User = Depends(get_current_user)):
    r = Role(name=body.name, description=body.description)
    session.add(r)
    await session.flush()
    await record_audit(
        session,
        user_id=admin.id,
        action="role.create",
        resource_type="role",
        resource_id=str(r.id),
        details={"name": r.name},
    )
    return ok({"id": str(r.id)}, message="Role created")


@router.patch("/roles/{role_id}", dependencies=[Depends(require_permissions(PERM_ROLES_WRITE))])
async def update_role(session: DbSession, role_id: uuid.UUID, body: RoleUpdate, admin: User = Depends(get_current_user)):
    r = (await session.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Role not found")
    if body.name is not None and body.name != r.name:
        exists = (await session.execute(select(Role).where(Role.name == body.name, Role.id != role_id))).scalar_one_or_none()
        if exists is not None:
            raise ConflictError("Role name already exists")
        r.name = body.name
    if body.description is not None:
        r.description = body.description
    await record_audit(session, user_id=admin.id, action="role.update", resource_type="role", resource_id=str(role_id))
    return ok(message="Role updated")


@router.delete("/roles/{role_id}", dependencies=[Depends(require_permissions(PERM_ROLES_WRITE))])
async def delete_role(session: DbSession, role_id: uuid.UUID, admin: User = Depends(get_current_user)):
    r = (await session.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Role not found")
    n_users = int(
        (await session.execute(select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id))).scalar_one(),
    )
    if n_users > 0:
        raise ConflictError("Cannot delete role assigned to users")
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    await session.execute(delete(Role).where(Role.id == role_id))
    await record_audit(session, user_id=admin.id, action="role.delete", resource_type="role", resource_id=str(role_id))
    return ok(message="Role deleted")


@router.put("/roles/{role_id}/permissions", dependencies=[Depends(require_permissions(PERM_ROLES_WRITE))])
async def set_role_permissions(
    session: DbSession,
    role_id: uuid.UUID,
    body: RolePermissionsBody,
    admin: User = Depends(get_current_user),
):
    role = (await session.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if role is None:
        raise NotFoundError("Role not found")
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for pid in body.permission_ids:
        session.add(RolePermission(role_id=role_id, permission_id=pid))
    await session.flush()
    await record_audit(
        session,
        user_id=admin.id,
        action="role.permissions_set",
        resource_type="role",
        resource_id=str(role_id),
        details={"permission_ids": [str(x) for x in body.permission_ids]},
    )
    return ok(message="Permissions updated")
