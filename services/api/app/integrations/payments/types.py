"""Normalized schemas for payment providers — integration contracts for webhooks and initiate responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InitiatePaymentProviderBody(BaseModel):
    """Shape returned by ``initiate_payment`` (serialized for API / logs; avoids leaking secrets)."""

    model_config = ConfigDict(extra="allow")

    provider: str | None = None
    order_reference: str | None = None
    external_reference: str | None = Field(None, description="Gateway transaction / collection id when known")
    redirect_url: str | None = None
    status: str | None = Field(None, description="Provider-specific status string")
    raw: dict[str, Any] = Field(default_factory=dict, description="Subset safe to echo to clients")


class WebhookVerificationResult(BaseModel):
    """Result of signature / checksum verification + normalized routing fields (no business side effects)."""

    model_config = ConfigDict(extra="forbid")

    signature_valid: bool
    provider_event_type: str | None = None
    order_reference: str | None = None
    provider_transaction_id: str | None = Field(
        None,
        description="Stable id from gateway for webhook deduplication when present",
    )
    gateway_status: str | None = Field(None, description="Provider status field if any")
    normalized_outcome: Literal["success", "failure", "pending", "unknown"] = "unknown"
    notes: str | None = Field(None, description="Provider-specific hint for observability")


def summarize_payload_for_logs(payload: dict[str, Any], *, max_keys: int = 25) -> dict[str, Any]:
    """Drop bulky / sensitive-looking keys from webhook payloads for audit logs."""
    skip = frozenset({"card", "pan", "cvv", "checksum", "signature", "password", "secret", "token"})
    out: dict[str, Any] = {}
    for i, k in enumerate(sorted(payload.keys())):
        if i >= max_keys:
            out["_truncated"] = True
            break
        lk = str(k).lower()
        if any(s in lk for s in skip):
            out[k] = "[redacted]"
        elif isinstance(payload[k], dict):
            out[k] = {"_type": "object", "keys": list(payload[k].keys())[:10]}
        else:
            v = payload[k]
            out[k] = str(v)[:200] if v is not None else None
    return out
