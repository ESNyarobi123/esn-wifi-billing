from __future__ import annotations

from typing import Any

import httpx

from app.core.exceptions import AppError, ValidationAppError


class ProviderIntegrationError(AppError):
    """Normalized failure calling a payment provider (HTTP / configuration)."""

    def __init__(self, message: str, *, provider: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="provider_integration_error", status_code=502)
        self.provider = provider
        self.details = details or {}


def normalize_provider_http_error(exc: BaseException, *, provider: str) -> ProviderIntegrationError:
    if isinstance(exc, ValidationAppError):
        raise exc
    if isinstance(exc, httpx.TimeoutException):
        return ProviderIntegrationError("Provider request timed out", provider=provider, details={"type": "timeout"})
    if isinstance(exc, httpx.HTTPStatusError):
        return ProviderIntegrationError(
            f"Provider HTTP {exc.response.status_code}",
            provider=provider,
            details={"status_code": exc.response.status_code},
        )
    if isinstance(exc, httpx.RequestError):
        return ProviderIntegrationError(str(exc), provider=provider, details={"type": "request_error"})
    if isinstance(exc, RuntimeError):
        return ProviderIntegrationError(str(exc), provider=provider, details={"type": "runtime"})
    return ProviderIntegrationError(str(exc), provider=provider, details={"type": "unknown"})
