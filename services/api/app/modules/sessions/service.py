from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SessionStatus
from app.modules.sessions.models import HotspotSession


def _norm_mac(raw: str | None) -> str:
    if not raw:
        return ""
    return str(raw).upper().replace("-", ":")


def _prune_active_sessions_not_in_seen(
    active_sessions: list[HotspotSession],
    seen: set[tuple[str, str]],
) -> int:
    pruned = 0
    for hs in active_sessions:
        key = (hs.mac_address, hs.external_session_id or "")
        if key not in seen:
            hs.status = SessionStatus.expired.value
            pruned += 1
    return pruned


async def ingest_hotspot_sessions_from_router(
    session: AsyncSession,
    *,
    router_id: uuid.UUID,
    live_rows: list[dict[str, Any]],
    prune_missing: bool = False,
) -> dict[str, int]:
    """Upsert active hotspot rows from the MikroTik integration layer."""
    now = datetime.now(UTC)
    created = 0
    updated = 0
    seen: set[tuple[str, str]] = set()

    for row in live_rows:
        mac = _norm_mac(row.get("mac_address") or row.get("mac"))
        if not mac:
            continue
        ext = str(row.get("id") or row.get("session_id") or "").strip() or None
        ip = row.get("ip_address") or row.get("ip")
        user = row.get("user") or row.get("username")
        bu = int(row.get("bytes_up") or row.get("upload") or 0)
        bd = int(row.get("bytes_down") or row.get("download") or 0)
        key = (mac, ext or "")
        seen.add(key)

        hs: HotspotSession | None = None
        if ext:
            hs = (
                await session.execute(
                    select(HotspotSession).where(
                        HotspotSession.router_id == router_id,
                        HotspotSession.external_session_id == ext,
                        HotspotSession.status == SessionStatus.active.value,
                    ),
                )
            ).scalar_one_or_none()
        if hs is None:
            hs = (
                await session.execute(
                    select(HotspotSession).where(
                        HotspotSession.router_id == router_id,
                        HotspotSession.mac_address == mac,
                        HotspotSession.status == SessionStatus.active.value,
                    ),
                )
            ).scalar_one_or_none()

        if hs is None:
            hs = HotspotSession(
                router_id=router_id,
                mac_address=mac,
                ip_address=str(ip) if ip else None,
                username=str(user) if user else None,
                external_session_id=ext,
                login_at=now,
                expires_at=None,
                bytes_up=bu,
                bytes_down=bd,
                status=SessionStatus.active.value,
            )
            session.add(hs)
            created += 1
        else:
            hs.ip_address = str(ip) if ip else hs.ip_address
            hs.username = str(user) if user else hs.username
            if ext:
                hs.external_session_id = ext
            hs.bytes_up = bu
            hs.bytes_down = bd
            updated += 1

    pruned = 0
    if prune_missing:
        active = (
            await session.execute(
                select(HotspotSession).where(
                    HotspotSession.router_id == router_id,
                    HotspotSession.status == SessionStatus.active.value,
                ),
            )
        ).scalars().all()
        pruned = _prune_active_sessions_not_in_seen(list(active), seen)

    await session.flush()
    return {"created": created, "updated": updated, "pruned": pruned, "live_count": len(live_rows)}
