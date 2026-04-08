"""RouterOS command helpers and payload parsers for the supported ESN HotSpot operations."""

from __future__ import annotations

import re
from typing import Any


_UPTIME_PARTS = re.compile(r"(?:(?P<weeks>\d+)w)?(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?")


def parse_routeros_uptime(raw: str | None) -> int | None:
    value = (raw or "").strip()
    if not value:
        return None
    match = _UPTIME_PARTS.fullmatch(value)
    if not match:
        return None
    weeks = int(match.group("weeks") or 0)
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return seconds + (minutes * 60) + (hours * 3600) + ((days + weeks * 7) * 86400)


def normalize_mac(raw: str | None) -> str:
    return str(raw or "").strip().upper().replace("-", ":")


def parse_int(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def build_rate_limit(*, bandwidth_up_kbps: int | None, bandwidth_down_kbps: int | None) -> str | None:
    """
    RouterOS ``rate-limit`` syntax is ``rx-rate/tx-rate``.
    For a hotspot customer, ``rx`` maps to upload from the router perspective and ``tx`` to download.
    """
    if not bandwidth_up_kbps and not bandwidth_down_kbps:
        return None
    up = max(int(bandwidth_up_kbps or 0), 0)
    down = max(int(bandwidth_down_kbps or 0), 0)
    return f"{up}k/{down}k"


def parse_system_resource(row: dict[str, str]) -> dict[str, Any]:
    free_memory = parse_int(row.get("free-memory"))
    total_memory = parse_int(row.get("total-memory"))
    return {
        "cpu_load_percent": float(parse_int(row.get("cpu-load")) or 0),
        "free_memory_bytes": free_memory,
        "total_memory_bytes": total_memory,
        "uptime_seconds": parse_routeros_uptime(row.get("uptime")),
        "board_name": row.get("board-name"),
        "version": row.get("version"),
        "architecture_name": row.get("architecture-name"),
        "raw": row,
    }


def parse_active_session(row: dict[str, str]) -> dict[str, Any]:
    return {
        "id": row.get(".id") or row.get("id") or "",
        "user": row.get("user") or row.get("name"),
        "mac_address": normalize_mac(row.get("mac-address")),
        "ip_address": row.get("address"),
        "uptime_secs": parse_routeros_uptime(row.get("uptime")) or 0,
        "bytes_up": parse_int(row.get("bytes-in")) or 0,
        "bytes_down": parse_int(row.get("bytes-out")) or 0,
        "server": row.get("server"),
    }
