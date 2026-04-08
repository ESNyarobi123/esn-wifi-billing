from __future__ import annotations

import hashlib
import json
from typing import Any

from app.integrations.payments.types import WebhookVerificationResult


def compute_webhook_dedupe_key(*, provider: str, payload: dict[str, Any], result: WebhookVerificationResult) -> str:
    """Stable key for replay protection (per provider webhook)."""
    if result.provider_transaction_id:
        return f"{provider}:txn:{result.provider_transaction_id}"
    if result.order_reference:
        inner = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        ev = (result.provider_event_type or payload.get("event") or inner.get("event") or "") or "na"
        st = (result.gateway_status or inner.get("status") or "") or "na"
        return f"{provider}:ord:{result.order_reference}:{ev}:{st}"
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    h = hashlib.sha256(f"{provider}:{canonical}".encode()).hexdigest()
    return f"{provider}:payload:{h[:48]}"
