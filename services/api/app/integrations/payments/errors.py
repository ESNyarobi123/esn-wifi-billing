from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.exceptions import AppError, ValidationAppError


class ProviderIntegrationError(AppError):
    """Normalized failure calling a payment provider (HTTP / configuration)."""

    def __init__(self, message: str, *, provider: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="provider_integration_error", status_code=502)
        self.provider = provider
        self.details = details or {}


def _extract_provider_http_error_message(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        payload = None

    candidates: list[str] = []
    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "statusMessage"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("message", "error", "detail", "statusMessage"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
    text = response.text.strip()
    if text:
        candidates.append(text[:400])

    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            return candidate
    return None


def normalize_provider_http_error(exc: BaseException, *, provider: str) -> ProviderIntegrationError:
    if isinstance(exc, ValidationAppError):
        raise exc
    if isinstance(exc, httpx.TimeoutException):
        return ProviderIntegrationError("Provider request timed out", provider=provider, details={"type": "timeout"})
    if isinstance(exc, httpx.HTTPStatusError):
        provider_message = _extract_provider_http_error_message(exc.response)
        message = f"Provider HTTP {exc.response.status_code}"
        if provider_message:
            message = f"{message}: {provider_message}"
        return ProviderIntegrationError(
            message,
            provider=provider,
            details={"status_code": exc.response.status_code, "provider_message": provider_message},
        )
    if isinstance(exc, httpx.RequestError):
        return ProviderIntegrationError(str(exc), provider=provider, details={"type": "request_error"})
    if isinstance(exc, RuntimeError):
        return ProviderIntegrationError(str(exc), provider=provider, details={"type": "runtime"})
    return ProviderIntegrationError(str(exc), provider=provider, details={"type": "unknown"})
