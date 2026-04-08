from __future__ import annotations


class MikrotikIntegrationError(Exception):
    """Raised by NAS adapters / resilience wrapper — converted to structured ``nas`` blobs in router_operations."""

    def __init__(self, message: str, *, code: str, retryable: bool = True):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable

    def to_payload(self) -> dict:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}
