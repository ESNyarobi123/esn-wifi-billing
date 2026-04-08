from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.modules.access_control.models import Role, RolePermission, UserRole
from app.modules.auth.models import User

_bearer = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncSession:
    async for s in get_db():
        yield s


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> uuid.UUID:
    if creds is None or not creds.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = decode_token(creds.credentials)
    except JWTError as e:
        raise UnauthorizedError("Invalid token") from e
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid token subject")
    try:
        return uuid.UUID(str(sub))
    except ValueError as e:
        raise UnauthorizedError("Invalid token subject") from e


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]


async def get_current_user(
    session: DbSession,
    user_id: CurrentUserId,
) -> User:
    stmt = (
        select(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .options(
            selectinload(User.roles).selectinload(UserRole.role).selectinload(Role.permissions).selectinload(
                RolePermission.permission
            ),
        )
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def user_permission_codes(user: User) -> set[str]:
    codes: set[str] = set()
    for ur in user.roles:
        for rp in ur.role.permissions:
            codes.add(rp.permission.code)
    return codes


async def get_user_permissions(user: CurrentUser) -> set[str]:
    return await user_permission_codes(user)


UserPermissions = Annotated[set[str], Depends(get_user_permissions)]


def require_permissions(*required: str) -> Callable[..., None]:
    async def _dep(perms: set[str] = Depends(get_user_permissions)) -> None:
        missing = [p for p in required if p not in perms]
        if missing:
            raise ForbiddenError(f"Missing permission(s): {', '.join(missing)}")

    return _dep


def require_any_permission(*required: str) -> Callable[..., None]:
    async def _dep(perms: set[str] = Depends(get_user_permissions)) -> None:
        if not any(p in perms for p in required):
            raise ForbiddenError("Insufficient permissions")

    return _dep


OptionalCreds = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


async def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else None
