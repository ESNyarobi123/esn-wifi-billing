from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.payments.checksum import clickpesa_payload_checksum
from app.integrations.payments.clickpesa import ClickPesaProvider
from app.integrations.payments.errors import normalize_provider_http_error
from app.modules.payments.service import refresh_payment_status_from_provider


@pytest.mark.asyncio
async def test_clickpesa_initiate_payment_live_flow(monkeypatch):
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_enabled", True)
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_api_base_url", "https://api.clickpesa.com")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_client_id", "client-1")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_api_key", "api-key-1")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_client_secret", "")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_checksum_key", "sum-key")

    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else None
        calls.append((request.method, request.url.path, body))

        if request.url.path == "/third-parties/generate-token":
            assert request.headers["client-id"] == "client-1"
            assert request.headers["api-key"] == "api-key-1"
            return httpx.Response(200, json={"success": True, "token": "provider-token"})

        assert request.headers["authorization"] == "Bearer provider-token"
        if request.url.path == "/third-parties/payments/preview-ussd-push-request":
            assert body is not None
            expected = clickpesa_payload_checksum(
                "sum-key",
                {
                    "amount": "10000",
                    "currency": "TZS",
                    "orderReference": "ORD-1",
                    "phoneNumber": "255712345678",
                    "fetchSenderDetails": True,
                },
            )
            assert body["checksum"] == expected
            assert body["checksumMethod"] == "canonical"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "activeMethods": ["MPESA", "TIGOPESA"],
                        "sender": {"accountName": "Jane Doe"},
                    }
                },
            )

        if request.url.path == "/third-parties/payments/initiate-ussd-push-request":
            assert body is not None
            expected = clickpesa_payload_checksum(
                "sum-key",
                {
                    "amount": "10000",
                    "currency": "TZS",
                    "orderReference": "ORD-1",
                    "phoneNumber": "255712345678",
                },
            )
            assert body["checksum"] == expected
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "cp-1",
                        "status": "PROCESSING",
                        "paymentReference": "PAY-1",
                        "channel": "USSD_PUSH",
                    }
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    provider = ClickPesaProvider(transport=httpx.MockTransport(handler))
    result = await provider.initiate_payment(
        order_reference="ORD-1",
        amount="10000",
        currency="TZS",
        customer={"customerPhoneNumber": "+255 712 345 678"},
        callback_url="https://api.example.com/api/v1/payments/webhooks/clickpesa",
        metadata={"payment_id": "abc"},
    )

    assert [path for _, path, _ in calls] == [
        "/third-parties/generate-token",
        "/third-parties/payments/preview-ussd-push-request",
        "/third-parties/payments/initiate-ussd-push-request",
    ]
    assert result["provider"] == "clickpesa"
    assert result["status"] == "PROCESSING"
    assert result["external_reference"] == "cp-1"
    assert result["payment_reference"] == "PAY-1"
    assert result["phone_number"] == "255712345678"
    assert result["preview"]["active_methods"] == ["MPESA", "TIGOPESA"]


@pytest.mark.asyncio
async def test_clickpesa_query_payment_status_normalizes(monkeypatch):
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_api_base_url", "https://api.clickpesa.com")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_client_id", "client-1")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_api_key", "api-key-1")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_client_secret", "")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/third-parties/generate-token":
            return httpx.Response(200, json={"token": "provider-token"})
        if request.url.path == "/third-parties/payments/ORD-2":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "cp-2",
                        "status": "SETTLED",
                        "paymentReference": "PAY-2",
                        "orderReference": "ORD-2",
                    }
                ],
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    provider = ClickPesaProvider(transport=httpx.MockTransport(handler))
    result = await provider.query_payment_status(order_reference="ORD-2")

    assert result["gateway_status"] == "SETTLED"
    assert result["normalized_outcome"] == "success"
    assert result["provider_transaction_id"] == "cp-2"
    assert result["payment_reference"] == "PAY-2"


@pytest.mark.asyncio
async def test_clickpesa_tzs_amount_normalized_to_whole_string(monkeypatch):
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_enabled", True)
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_api_base_url", "https://api.clickpesa.com")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_client_id", "client-1")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_api_key", "api-key-1")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_client_secret", "")
    monkeypatch.setattr("app.integrations.payments.clickpesa.settings.clickpesa_checksum_key", "")

    seen_amounts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else None
        if request.url.path == "/third-parties/generate-token":
            return httpx.Response(200, json={"token": "provider-token"})
        if request.url.path == "/third-parties/payments/preview-ussd-push-request":
            seen_amounts.append(body["amount"])
            return httpx.Response(200, json={"data": {"activeMethods": ["MPESA"]}})
        if request.url.path == "/third-parties/payments/initiate-ussd-push-request":
            seen_amounts.append(body["amount"])
            return httpx.Response(200, json={"data": {"id": "cp-1", "status": "PROCESSING"}})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    provider = ClickPesaProvider(transport=httpx.MockTransport(handler))
    await provider.initiate_payment(
        order_reference="ORD-100",
        amount="1000.00",
        currency="TZS",
        customer={"customerPhoneNumber": "0712345678"},
        callback_url=None,
        metadata=None,
    )

    assert seen_amounts == ["1000", "1000"]


def test_normalize_provider_http_error_includes_response_message():
    request = httpx.Request("POST", "https://api.clickpesa.com/third-parties/payments/initiate-ussd-push-request")
    response = httpx.Response(400, request=request, json={"message": "Invalid phone number"})
    exc = httpx.HTTPStatusError("bad request", request=request, response=response)

    normalized = normalize_provider_http_error(exc, provider="clickpesa")

    assert normalized.message == "Provider HTTP 400: Invalid phone number"
    assert normalized.details["status_code"] == 400
    assert normalized.details["provider_message"] == "Invalid phone number"


@pytest.mark.asyncio
async def test_refresh_payment_status_from_provider_applies_success():
    payment = SimpleNamespace(
        id=uuid.uuid4(),
        provider="clickpesa",
        order_reference="ORD-3",
        provider_ref=None,
        payment_status="pending",
    )
    provider = MagicMock()
    provider.query_payment_status = AsyncMock(
        return_value={
            "provider": "clickpesa",
            "order_reference": "ORD-3",
            "gateway_status": "SUCCESS",
            "normalized_outcome": "success",
            "provider_transaction_id": "cp-3",
            "payment_reference": "PAY-3",
            "records": [{"id": "cp-3", "status": "SUCCESS"}],
            "raw": {"id": "cp-3", "status": "SUCCESS"},
        }
    )
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    with (
        patch("app.modules.payments.service.get_payment_provider", return_value=provider),
        patch("app.modules.payments.service.apply_payment_success", new=AsyncMock(return_value={"activated": True})) as success_mock,
        patch("app.modules.payments.service.apply_payment_failed", new=AsyncMock()) as failed_mock,
    ):
        result = await refresh_payment_status_from_provider(session, payment)

    success_mock.assert_awaited_once()
    failed_mock.assert_not_awaited()
    assert payment.provider_ref == "PAY-3"
    assert result["payment_status"] == "pending"
    assert result["normalized_outcome"] == "success"
    assert session.add.called
