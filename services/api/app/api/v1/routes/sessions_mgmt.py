from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError
from app.core.responses import ok
from app.db.enums import SessionStatus
from app.integrations.mikrotik.factory import get_mikrotik_adapter
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_SESSIONS_READ, PERM_SESSIONS_TERMINATE
from app.modules.auth.models import User
from app.modules.routers.models import Router
from app.modules.sessions.models import HotspotSession

router = APIRouter()


class SessionFlagBody(BaseModel):
    reason: str | None = None
    flags: dict[str, Any] | None = None


@router.get("/sessions", dependencies=[Depends(require_permissions(PERM_SESSIONS_READ))])
async def list_sessions(session: DbSession, _u: User = Depends(get_current_user), active_only: bool = True):
    stmt = select(HotspotSession).order_by(HotspotSession.login_at.desc())
    if active_only:
        stmt = stmt.where(HotspotSession.status == SessionStatus.active.value)
    rows = (await session.execute(stmt.limit(200))).scalars().all()
    return ok(
        [
            {
                "id": str(s.id),
                "router_id": str(s.router_id),
                "mac_address": s.mac_address,
                "username": s.username,
                "login_at": s.login_at.isoformat(),
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "status": s.status,
                "bytes_up": s.bytes_up,
                "bytes_down": s.bytes_down,
            }
            for s in rows
        ],
    )


@router.get("/sessions/{session_id}", dependencies=[Depends(require_permissions(PERM_SESSIONS_READ))])
async def get_session(session: DbSession, session_id: uuid.UUID, _u: User = Depends(get_current_user)):
    s = (await session.execute(select(HotspotSession).where(HotspotSession.id == session_id))).scalar_one_or_none()
    if s is None:
        raise NotFoundError("Session not found")
    router = (await session.execute(select(Router).where(Router.id == s.router_id))).scalar_one_or_none()
    return ok(
        {
            "id": str(s.id),
            "router": {"id": str(router.id), "name": router.name, "host": router.host} if router else None,
            "mac_address": s.mac_address,
            "username": s.username,
            "login_at": s.login_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "status": s.status,
            "bytes_up": s.bytes_up,
            "bytes_down": s.bytes_down,
        },
    )


@router.post("/sessions/{session_id}/terminate", dependencies=[Depends(require_permissions(PERM_SESSIONS_TERMINATE))])
async def terminate_session(session: DbSession, session_id: uuid.UUID, admin: User = Depends(get_current_user)):
    s = (await session.execute(select(HotspotSession).where(HotspotSession.id == session_id))).scalar_one_or_none()
    if s is None:
        raise NotFoundError("Session not found")
    r = (await session.execute(select(Router).where(Router.id == s.router_id))).scalar_one_or_none()
    if r:
        adapter = get_mikrotik_adapter(r)
        if s.external_session_id:
            await adapter.disconnect_hotspot_user(session_id=s.external_session_id)
        else:
            await adapter.disconnect_hotspot_user(mac=s.mac_address)
    s.status = SessionStatus.terminated.value
    await record_audit(
        session,
        user_id=admin.id,
        action="session.terminate",
        resource_type="hotspot_session",
        resource_id=str(session_id),
    )
    return ok(message="Session terminated")


@router.post("/sessions/{session_id}/flag-suspicious", dependencies=[Depends(require_permissions(PERM_SESSIONS_TERMINATE))])
async def flag_session_suspicious(
    session: DbSession,
    session_id: uuid.UUID,
    body: SessionFlagBody,
    admin: User = Depends(get_current_user),
):
    s = (await session.execute(select(HotspotSession).where(HotspotSession.id == session_id))).scalar_one_or_none()
    if s is None:
        raise NotFoundError("Session not found")
    merged = dict(s.flags or {})
    if body.flags:
        merged.update(body.flags)
    if body.reason:
        merged["suspicious_reason"] = body.reason
    s.flags = merged
    s.status = SessionStatus.suspicious.value
    await record_audit(
        session,
        user_id=admin.id,
        action="session.flag_suspicious",
        resource_type="hotspot_session",
        resource_id=str(session_id),
        details={"reason": body.reason},
    )
    return ok(message="Session flagged")
