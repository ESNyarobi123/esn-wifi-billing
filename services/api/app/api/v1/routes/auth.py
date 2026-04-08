from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.deps import CurrentUser, DbSession, get_client_ip
from app.core.responses import dump_model, ok
from app.modules.access_control.audit_service import record_audit
from app.modules.auth.schemas import (
    LoginRequest,
    MeProfileUpdate,
    PasswordChangeRequest,
    RefreshRequest,
    TokenPair,
    UserPublic,
)
from app.modules.auth.service import change_password, login, refresh_tokens, update_profile

router = APIRouter()


@router.post("/login")
async def auth_login(session: DbSession, body: LoginRequest):
    user, access, refresh = await login(session, body.email, body.password)
    return ok(
        {
            "user": dump_model(UserPublic.model_validate(user)),
            "tokens": TokenPair(access_token=access, refresh_token=refresh).model_dump(),
        },
        message="Logged in",
    )


@router.post("/refresh")
async def auth_refresh(body: RefreshRequest):
    access, refresh = await refresh_tokens(body.refresh_token)
    return ok(
        {"tokens": TokenPair(access_token=access, refresh_token=refresh).model_dump()},
        message="Token refreshed",
    )


@router.get("/me")
async def auth_me(user: CurrentUser):
    return ok(dump_model(UserPublic.model_validate(user)))


@router.patch("/me")
async def auth_patch_me(request: Request, session: DbSession, user: CurrentUser, body: MeProfileUpdate):
    await update_profile(session, user, full_name=body.full_name)
    await session.refresh(user)
    await record_audit(
        session,
        user_id=user.id,
        action="auth.profile_update",
        resource_type="user",
        resource_id=str(user.id),
        details={"full_name": body.full_name},
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return ok(dump_model(UserPublic.model_validate(user)), message="Profile updated")


@router.post("/me/password")
async def auth_change_password(request: Request, session: DbSession, user: CurrentUser, body: PasswordChangeRequest):
    await change_password(session, user, current_password=body.current_password, new_password=body.new_password)
    await record_audit(
        session,
        user_id=user.id,
        action="auth.password_change",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return ok(message="Password updated")
