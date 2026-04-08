from unittest.mock import MagicMock

from app.db.enums import SessionStatus
from app.modules.sessions.service import _norm_mac, _prune_active_sessions_not_in_seen


def test_norm_mac_normalizes():
    assert _norm_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert _norm_mac("") == ""


def test_prune_active_sessions_not_in_seen():
    seen = {("AA:BB:CC:DD:EE:01", "")}
    keep = MagicMock()
    keep.mac_address = "AA:BB:CC:DD:EE:01"
    keep.external_session_id = None
    keep.status = SessionStatus.active.value
    drop = MagicMock()
    drop.mac_address = "AA:BB:CC:DD:EE:02"
    drop.external_session_id = "s1"
    drop.status = SessionStatus.active.value
    n = _prune_active_sessions_not_in_seen([keep, drop], seen)
    assert n == 1
    assert drop.status == SessionStatus.expired.value
    assert keep.status == SessionStatus.active.value
