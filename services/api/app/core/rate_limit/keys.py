"""Stable, non-logging key material for Redis rate limit entries."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import uuid
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9._-]+", re.IGNORECASE)


def normalize_site_slug(site_slug: str) -> str:
    s = _SLUG_RE.sub("-", (site_slug or "").strip().lower())[:64]
    return s or "unknown"


def normalize_client_ip(ip: str | None) -> str:
    if not ip:
        return "unknown"
    raw = ip.strip()
    if raw.startswith("::ffff:") and "." in raw:
        raw = raw.removeprefix("::ffff:")
    try:
        addr = ipaddress.ip_address(raw)
        return addr.compressed
    except ValueError:
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]


def voucher_code_fingerprint(site_slug: str, code: str) -> str:
    norm_site = normalize_site_slug(site_slug)
    norm_code = (code or "").strip().upper()
    return hashlib.sha256(f"{norm_site}:{norm_code}".encode()).hexdigest()[:24]


def phone_fingerprint(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 5:
        return None
    return hashlib.sha256(digits.encode()).hexdigest()[:16]


def customer_segment(customer_id: uuid.UUID | None) -> str | None:
    if customer_id is None:
        return None
    return str(customer_id)


def mac_fingerprint(mac: str) -> str:
    m = (mac or "").upper().replace("-", ":").strip()
    return hashlib.sha256(m.encode()).hexdigest()[:16]


def build_portal_rate_key(
    *,
    prefix: str,
    action: str,
    site_slug: str,
    client_ip: str | None,
    customer_id: uuid.UUID | None = None,
    voucher_fp: str | None = None,
    phone_fp: str | None = None,
    mac_fp: str | None = None,
) -> str:
    """Redis key string (opaque); keep cardinality bounded."""
    parts: list[str] = [prefix, "portal", "v1", action, normalize_site_slug(site_slug), normalize_client_ip(client_ip)]
    c = customer_segment(customer_id)
    if c:
        parts.append(f"c:{c}")
    if voucher_fp:
        parts.append(f"v:{voucher_fp}")
    if phone_fp:
        parts.append(f"p:{phone_fp}")
    if mac_fp:
        parts.append(f"m:{mac_fp}")
    return ":".join(parts)
