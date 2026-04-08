"""ClickPesa-style payload checksum (HMAC-SHA256 over canonical JSON).

See: https://docs.clickpesa.com/home/checksum
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def canonicalize(obj: Any) -> Any:
    if obj is None or not isinstance(obj, (dict, list)):
        return obj
    if isinstance(obj, list):
        return [canonicalize(item) for item in obj]
    return {key: canonicalize(obj[key]) for key in sorted(obj.keys())}


def clickpesa_payload_checksum(checksum_key: str, payload: dict[str, Any]) -> str:
    """Exclude ``checksum`` and ``checksumMethod`` from the payload before calling this."""
    body = json.dumps(canonicalize(payload), separators=(",", ":"), ensure_ascii=False)
    return hmac.new(checksum_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_clickpesa_checksum(checksum_key: str, body: dict[str, Any], *, expected: str | None) -> bool:
    if not expected:
        return False
    stripped = {k: v for k, v in body.items() if k not in ("checksum", "checksumMethod")}
    return hmac.compare_digest(clickpesa_payload_checksum(checksum_key, stripped), expected.lower())
