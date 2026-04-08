from __future__ import annotations

from app.core.config import settings
from app.integrations.payments.clickpesa import ClickPesaProvider
from app.integrations.payments.mock_provider import MockPaymentProvider
from app.integrations.payments.protocol import PaymentProvider


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    key = (name or settings.default_payment_provider or "mock").lower()
    if key == "clickpesa":
        return ClickPesaProvider()
    return MockPaymentProvider()
