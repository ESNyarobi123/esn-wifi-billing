from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.routers.monitoring_service import router_should_flip_offline


def test_router_should_flip_offline_respects_threshold():
    now = datetime.now(UTC)
    assert router_should_flip_offline(last_seen_at=now, is_online=True, now=now, threshold_seconds=300) is False
    assert (
        router_should_flip_offline(
            last_seen_at=now - timedelta(seconds=400),
            is_online=True,
            now=now,
            threshold_seconds=300,
        )
        is True
    )
    assert router_should_flip_offline(last_seen_at=None, is_online=True, now=now, threshold_seconds=300) is True
    assert router_should_flip_offline(last_seen_at=now, is_online=False, now=now, threshold_seconds=300) is False
