from __future__ import annotations

from typing import Any, Literal

from app.integrations.payments.types import WebhookVerificationResult


class MockPaymentProvider:
    name = "mock"

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
        return {
            "mock": True,
            "order_reference": order_reference,
            "amount": amount,
            "currency": currency,
            "payment_reference": f"MOCK-{order_reference}",
            "instructions": "Use POST /api/v1/payments/mock/complete with the order_reference to simulate success.",
        }

    async def verify_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> WebhookVerificationResult:
        ev = str(payload.get("event") or "MOCK")
        ev_u = ev.upper()
        norm: Literal["success", "failure", "pending", "unknown"] = "unknown"
        if "FAIL" in ev_u:
            norm = "failure"
        elif any(x in ev_u for x in ("SUCCESS", "COMPLETE", "MOCK_SUCCESS", "PAYMENT RECEIVED")):
            norm = "success"
        elif "PENDING" in ev_u:
            norm = "pending"
        return WebhookVerificationResult(
            signature_valid=True,
            provider_event_type=ev,
            order_reference=payload.get("order_reference") or payload.get("orderReference"),
            provider_transaction_id=str(payload["txn_id"]) if payload.get("txn_id") is not None else None,
            gateway_status=payload.get("status"),
            normalized_outcome=norm,
        )

    async def query_payment_status(self, *, order_reference: str) -> dict[str, Any]:
        return {
            "provider": self.name,
            "order_reference": order_reference,
            "gateway_status": "PENDING",
            "provider_transaction_id": f"MOCK-{order_reference}",
            "payment_reference": f"MOCK-{order_reference}",
            "records": [],
            "raw": {
                "status": "PENDING",
                "message": "Mock provider does not settle automatically; use the mock complete endpoint.",
            },
        }
