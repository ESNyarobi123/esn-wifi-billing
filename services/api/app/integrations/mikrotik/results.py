from __future__ import annotations

from typing import Any

from app.integrations.mikrotik.errors import MikrotikIntegrationError


def nas_ok(**extra: Any) -> dict[str, Any]:
    return {"ok": True, **extra}


def nas_fail(err: MikrotikIntegrationError) -> dict[str, Any]:
    return {"ok": False, **err.to_payload()}
