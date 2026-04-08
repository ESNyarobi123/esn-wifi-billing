from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.integrations.payments.types import WebhookVerificationResult


@runtime_checkable
class PaymentProvider(Protocol):
    """Contract for PSP adapters: map-only in ``verify_webhook``; business activation lives in ``callback_pipeline``."""

    name: str

    async def initiate_payment(
        self,
        *,
        order_reference: str,
        amount: str,
        currency: str,
        customer: dict[str, Any],
        callback_url: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Return provider response dict (redirect URL, ref, etc.)."""
        ...

    async def verify_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> WebhookVerificationResult:
        """Verify signature/checksum and normalize routing fields (order ref, txn id, outcome). No DB writes."""
        ...

    async def query_payment_status(self, *, order_reference: str) -> dict[str, Any]:
        """Query the provider for the latest payment state using the merchant order reference."""
        ...
