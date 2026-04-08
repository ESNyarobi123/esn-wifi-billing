from __future__ import annotations

import re
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.integrations.payments.checksum import clickpesa_payload_checksum, verify_clickpesa_checksum
from app.integrations.payments.types import WebhookVerificationResult


def _normalize_clickpesa_base_url(value: str) -> str:
    base = value.rstrip("/")
    if base.endswith("/third-parties"):
        return base
    return f"{base}/third-parties"


def _normalize_phone_number(raw: str | None) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("255") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return f"255{digits[1:]}"
    raise ValidationAppError("ClickPesa requires a valid phone number in Tanzania country-code format, e.g. 255712345678.")


def _normalize_gateway_status(raw: str | None) -> str | None:
    status = str(raw or "").strip().upper()
    return status or None


def _normalized_outcome_from_status(raw: str | None) -> Literal["success", "failure", "pending", "unknown"]:
    status = _normalize_gateway_status(raw)
    if status in {"SUCCESS", "SETTLED"}:
        return "success"
    if status in {"FAILED", "REFUNDED", "REVERSED"}:
        return "failure"
    if status in {"PROCESSING", "PENDING", "AUTHORIZED"}:
        return "pending"
    return "unknown"


def _unwrap_clickpesa_body(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], (dict, list)):
        return payload["data"]
    return payload


class ClickPesaProvider:
    """Live ClickPesa collection integration: token, preview/initiate USSD push, query, and webhook verification."""

    name = "clickpesa"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base = _normalize_clickpesa_base_url(settings.clickpesa_api_base_url)
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=30.0, transport=self._transport)

    def _api_key(self) -> str:
        key = settings.clickpesa_effective_api_key
        if not key:
            raise RuntimeError("ClickPesa API key is not configured (set CLICKPESA_API_KEY).")
        return key

    def _client_id(self) -> str:
        client_id = settings.clickpesa_client_id.strip()
        if not client_id:
            raise RuntimeError("ClickPesa client ID is not configured (set CLICKPESA_CLIENT_ID).")
        return client_id

    def _with_checksum(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = settings.clickpesa_checksum_key.strip()
        if not key:
            return payload
        body = dict(payload)
        body["checksum"] = clickpesa_payload_checksum(key, body)
        body["checksumMethod"] = "HMAC_SHA256"
        return body

    async def _generate_token(self) -> str:
        async with self._client() as client:
            response = await client.post(
                "/generate-token",
                headers={
                    "client-id": self._client_id(),
                    "api-key": self._api_key(),
                },
            )
            response.raise_for_status()
            payload = response.json()
            body = _unwrap_clickpesa_body(payload)
            token = ""
            if isinstance(body, dict):
                token = str(body.get("token") or "").strip()
            if not token:
                raise RuntimeError("ClickPesa generate-token response did not include a token.")
            return token if token.startswith("Bearer ") else f"Bearer {token}"

    async def _authorized_request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        bearer = token or await self._generate_token()
        async with self._client() as client:
            response = await client.request(
                method,
                path,
                headers={"Authorization": bearer},
                json=json,
            )
            response.raise_for_status()
            return response

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
        if not settings.clickpesa_enabled:
            raise RuntimeError("ClickPesa is disabled (CLICKPESA_ENABLED=false)")

        if str(currency).strip().upper() != "TZS":
            raise ValidationAppError("ClickPesa USSD push currently supports TZS only.")

        phone_number = _normalize_phone_number(customer.get("customerPhoneNumber"))
        token = await self._generate_token()

        preview_payload = self._with_checksum(
            {
                "amount": str(amount),
                "currency": "TZS",
                "orderReference": order_reference,
                "phoneNumber": phone_number,
                "fetchSenderDetails": True,
            },
        )
        preview_res = await self._authorized_request(
            "POST",
            "/payments/preview-ussd-push-request",
            token=token,
            json=preview_payload,
        )
        preview_body = _unwrap_clickpesa_body(preview_res.json())

        initiate_payload = self._with_checksum(
            {
                "amount": str(amount),
                "currency": "TZS",
                "orderReference": order_reference,
                "phoneNumber": phone_number,
            },
        )
        initiate_res = await self._authorized_request(
            "POST",
            "/payments/initiate-ussd-push-request",
            token=token,
            json=initiate_payload,
        )
        initiate_body = _unwrap_clickpesa_body(initiate_res.json())

        preview_map = preview_body if isinstance(preview_body, dict) else {}
        initiate_map = initiate_body if isinstance(initiate_body, dict) else {}
        active_methods = preview_map.get("activeMethods") if isinstance(preview_map.get("activeMethods"), list) else []
        sender = preview_map.get("sender") if isinstance(preview_map.get("sender"), dict) else None
        external_reference = str(initiate_map.get("id") or "") or None
        payment_reference = str(initiate_map.get("paymentReference") or "") or None
        status = _normalize_gateway_status(initiate_map.get("status"))

        return {
            "provider": self.name,
            "order_reference": order_reference,
            "external_reference": external_reference,
            "payment_reference": payment_reference,
            "status": status,
            "phone_number": phone_number,
            "callback_url": callback_url,
            "preview": {
                "active_methods": active_methods,
                "sender": sender,
            },
            "raw": {
                "preview": preview_body,
                "initiate": initiate_body,
                "metadata": metadata or {},
            },
        }

    async def query_payment_status(self, *, order_reference: str) -> dict[str, Any]:
        response = await self._authorized_request("GET", f"/payments/{order_reference}")
        records_raw = _unwrap_clickpesa_body(response.json())
        records = records_raw if isinstance(records_raw, list) else [records_raw]
        latest = records[0] if records else {}
        gateway_status = _normalize_gateway_status(latest.get("status")) if isinstance(latest, dict) else None
        provider_transaction_id = None
        payment_reference = None
        if isinstance(latest, dict):
            provider_transaction_id = str(latest.get("id") or "") or None
            payment_reference = str(latest.get("paymentReference") or "") or None

        return {
            "provider": self.name,
            "order_reference": order_reference,
            "gateway_status": gateway_status,
            "normalized_outcome": _normalized_outcome_from_status(gateway_status),
            "provider_transaction_id": provider_transaction_id,
            "payment_reference": payment_reference,
            "records": records,
            "raw": latest if isinstance(latest, dict) else {"records": records},
        }

    async def verify_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> WebhookVerificationResult:
        key = settings.clickpesa_checksum_key
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        order_ref = data.get("orderReference") or payload.get("orderReference")
        txn_raw = data.get("transactionId") or payload.get("transactionId") or data.get("id") or payload.get("id")
        event_raw = str(payload.get("event", "")).strip() or None
        status = _normalize_gateway_status(data.get("status") or payload.get("status"))

        if not key:
            sig_ok = True
            notes = "checksum_key_not_configured"
        else:
            notes = None
            expected = payload.get("checksum") or headers.get("x-clickpesa-checksum")
            sig_ok = verify_clickpesa_checksum(key, payload, expected=str(expected) if expected else None)

        ev_u = (event_raw or "").upper()
        norm = _normalized_outcome_from_status(status)
        if norm == "unknown":
            if "FAILED" in ev_u or "REVERSED" in ev_u or "REFUNDED" in ev_u:
                norm = "failure"
            elif "PAYMENT RECEIVED" in ev_u or "SUCCESS" in ev_u or "SETTLED" in ev_u:
                norm = "success"
            elif "PENDING" in ev_u or "PROCESSING" in ev_u or "AUTHORIZED" in ev_u:
                norm = "pending"

        return WebhookVerificationResult(
            signature_valid=sig_ok,
            provider_event_type=event_raw,
            order_reference=str(order_ref) if order_ref else None,
            provider_transaction_id=str(txn_raw) if txn_raw else None,
            gateway_status=status,
            normalized_outcome=norm,
            notes=notes,
        )
