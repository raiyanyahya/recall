from redact import redact


def test_redacts_common_secret_shapes():
    samples = [
        "key sk-ant-ABCDEFGHIJKLMNOP1234567890",
        "aws AKIAIOSFODNN7EXAMPLE here",
        "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
        "Authorization: Bearer abcdef0123456789ABCDEF",
        "export API_KEY=supersecretvalue123",
        "DB_PASSWORD = hunter2hunter2",
    ]
    for s in samples:
        assert "[REDACTED]" in redact(s), s


def test_leaves_ordinary_text_alone():
    text = "We refactored db.py and ran pytest -q. All 12 tests pass."
    assert redact(text) == text


def test_handles_empty():
    assert redact("") == ""
    assert redact(None) is None
