from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token_optional_type,
    hash_password,
    verify_password,
)
from app.modules.access_control.models import UserRole
from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    stmt = select(User).where(User.email == email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def login(session: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    user = await authenticate_user(session, email, password)
    if user is None:
        raise UnauthorizedError("Invalid credentials")
    user.last_login_at = datetime.now(UTC)
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return user, access, refresh


async def refresh_tokens(refresh_token: str) -> tuple[str, str]:
    try:
        payload = decode_token_optional_type(refresh_token, "refresh")
    except ValueError as e:
        raise UnauthorizedError("Invalid refresh token") from e
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid refresh token")
    access = create_access_token(str(sub))
    new_refresh = create_refresh_token(str(sub))
    return access, new_refresh


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(UserRole.role),
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(session: AsyncSession, data: UserCreate, *, password: str | None = None) -> User:
    pwd = password or data.password
    user = User(
        email=data.email,
        password_hash=hash_password(pwd),
        full_name=data.full_name,
    )
    session.add(user)
    await session.flush()
    return user


async def update_profile(session: AsyncSession, user: User, *, full_name: str) -> User:
    user.full_name = full_name
    await session.flush()
    return user


async def change_password(session: AsyncSession, user: User, *, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise UnauthorizedError("Current password is incorrect")
    if current_password == new_password:
        raise ValidationAppError("New password must differ from the current password")
    user.password_hash = hash_password(new_password)
    await session.flush()
