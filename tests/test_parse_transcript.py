import parse_transcript as p


def test_parse_lines_skips_malformed_without_raising():
    # A mix of junk that must be ignored, with two real events that must survive.
    lines = [
        "123",                                              # bare JSON number
        '"a bare string"',                                  # bare JSON string
        "[1, 2, 3]",                                        # bare JSON array
        "{not valid json",                                  # not JSON at all
        '{"type": "assistant", "message": "oops-not-a-dict"}',   # message not a dict
        '{"type": "assistant", "message": {"content": '
        '[{"type": "tool_use", "name": "Bash", "input": [1, 2]}]}}',  # bad tool input
        '{"type": "user", "message": {"role": "user", "content": "real prompt"}}',
        '{"type": "assistant", "message": {"role": "assistant", '
        '"content": [{"type": "text", "text": "a real reply"}]}}',
    ]
    events = p.parse_lines(lines)  # must not raise
    pairs = {(e["role"], e["text"]) for e in events}
    assert ("user", "real prompt") in pairs
    assert ("assistant", "a real reply") in pairs


def test_tool_event_tolerates_non_dict_input():
    ev = p._tool_event({"type": "tool_use", "name": "Bash", "input": "not-a-dict"})
    assert ev["tool"] == "Bash"
    assert ev["detail"] == ""
    assert ev["files"] == []
