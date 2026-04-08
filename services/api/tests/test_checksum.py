from app.integrations.payments.checksum import clickpesa_payload_checksum, verify_clickpesa_checksum


def test_clickpesa_checksum_stable_ordering():
    key = "secret-key"
    payload = {"z": 1, "a": {"b": 2, "y": 3}}
    c1 = clickpesa_payload_checksum(key, payload)
    c2 = clickpesa_payload_checksum(key, {"a": {"y": 3, "b": 2}, "z": 1})
    assert c1 == c2


def test_verify_checksum():
    key = "k"
    payload = {"event": "X", "checksum": "ignore", "checksumMethod": "ignore", "a": 1}
    # build expected from stripped payload
    stripped = {k: v for k, v in payload.items() if k not in ("checksum", "checksumMethod")}
    expected = clickpesa_payload_checksum(key, stripped)
    full = {"event": "X", "a": 1, "checksum": expected, "checksumMethod": "canonical"}
    assert verify_clickpesa_checksum(key, full, expected=full["checksum"]) is True
