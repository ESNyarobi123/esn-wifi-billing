import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.notifications.service import notify_customer_payment


@pytest.mark.asyncio
async def test_notify_customer_payment_success():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    pay = MagicMock()
    pay.id = uuid.uuid4()
    pay.order_reference = "ORD-1"
    pay.amount = 1000
    pay.currency = "TZS"
    n = await notify_customer_payment(
        session,
        customer_id=uuid.uuid4(),
        payment=pay,
        success=True,
    )
    assert n.type == "payment_success"
    session.add.assert_called_once()
    session.flush.assert_awaited_once()
