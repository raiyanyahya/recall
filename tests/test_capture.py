import json
import os

import common
from _util import assistant, make_jsonl, run_capture, user
from config import load_config


def _history(cwd):
    """Every per-session log in this (single-test) project, concatenated."""
    d = os.path.join(common.output_dir(cwd, load_config(cwd)), "history")
    if not os.path.isdir(d):
        return ""
    return "".join(common.read_text(os.path.join(d, f)) for f in sorted(os.listdir(d)))


def test_incremental_capture_dedupes_header_and_redacts(tmp_path):
    cwd = str(tmp_path)
    t = os.path.join(cwd, "sessAAAA1111.jsonl")

    make_jsonl(t, [
        user("Build a login API"),
        assistant("Created the login route.", [("Write", {"file_path": "login.py"})]),
    ])
    run_capture(cwd, t, "sessAAAA1111")
    h1 = _history(cwd)
    assert h1.count("## Session sessAAAA") == 1
    assert "Build a login API" in h1 and "login.py" in h1

    # Append a second turn (with a secret that must be redacted on the way in).
    make_jsonl(t, [
        user("Build a login API"),
        assistant("Created the login route.", [("Write", {"file_path": "login.py"})]),
        user("Add password hashing"),
        assistant("Added bcrypt. Token sk-ant-ABCDEFGHIJKLMNOP123 must vanish."),
    ])
    run_capture(cwd, t, "sessAAAA1111")
    h2 = _history(cwd)
    assert h2.count("## Session sessAAAA") == 1, "duplicate session header"
    assert "Add password hashing" in h2 and "bcrypt" in h2
    assert "sk-ant-ABCDEFGHIJKLMNOP123" not in h2, "secret leaked into history"
    assert h2.count("**You:**") == 2


def test_partial_trailing_line_deferred_until_complete(tmp_path):
    cwd = str(tmp_path)
    t = os.path.join(cwd, "sessBBBB2222.jsonl")
    make_jsonl(t, [user("first complete turn")])
    run_capture(cwd, t, "sessBBBB2222")

    # A half-written line with no trailing newline must not be captured yet.
    with open(t, "a", encoding="utf-8") as fh:
        fh.write('{"type":"user","message":{"role":"user","content":"still writing"')
    run_capture(cwd, t, "sessBBBB2222")
    assert "still writing" not in _history(cwd)

    # Once the line is complete it is captured exactly once.
    with open(t, "a", encoding="utf-8") as fh:
        fh.write("}}\n")
    run_capture(cwd, t, "sessBBBB2222")
    assert _history(cwd).count("still writing") == 1


def test_capture_survives_malformed_transcript_line(tmp_path):
    # A corrupt JSONL line must not stall capture: the good turns around it still
    # get logged (a regression would silently break capture for the session).
    cwd = str(tmp_path)
    t = os.path.join(cwd, "sessFFFF6666.jsonl")
    with open(t, "w", encoding="utf-8") as fh:
        fh.write("12345\n")                                    # bare number, not an event
        fh.write(json.dumps(user("real work here")) + "\n")
        fh.write(json.dumps(assistant("did the work")) + "\n")
    run_capture(cwd, t, "sessFFFF6666")
    h = _history(cwd)
    assert "real work here" in h and "did the work" in h


def test_corrupt_offset_state_does_not_crash_capture(tmp_path):
    # A tampered .capture.json (non-int offset) must not crash capture; it just
    # re-captures the session from the top.
    cwd = str(tmp_path)
    cfg = load_config(cwd)
    common.ensure_output_dir(cwd, cfg)
    common.write_text(common.state_path(cwd, cfg), json.dumps({"sessGGGG7777": "bad"}))

    t = os.path.join(cwd, "sessGGGG7777.jsonl")
    make_jsonl(t, [user("recover cleanly"), assistant("ok")])
    run_capture(cwd, t, "sessGGGG7777")
    assert "recover cleanly" in _history(cwd)


def test_parallel_sessions_log_to_separate_files(tmp_path):
    # Two sessions in one project folder, turns interleaved: each must land in
    # its own file and never in the other one (they shared history.md before).
    cwd = str(tmp_path)
    ta = os.path.join(cwd, "aaaa1111-x.jsonl")
    tb = os.path.join(cwd, "bbbb2222-y.jsonl")
    make_jsonl(ta, [user("session A builds the invoice report")])
    run_capture(cwd, ta, "aaaa1111-x")
    make_jsonl(tb, [user("session B fixes the payroll import")])
    run_capture(cwd, tb, "bbbb2222-y")
    make_jsonl(ta, [user("session A builds the invoice report"), assistant("A adds totals")])
    run_capture(cwd, ta, "aaaa1111-x")
    cfg = load_config(cwd)
    a = common.read_text(common.history_path(cwd, cfg, "aaaa1111-x"))
    b = common.read_text(common.history_path(cwd, cfg, "bbbb2222-y"))
    assert "invoice report" in a and "A adds totals" in a and "payroll" not in a
    assert "payroll import" in b and "invoice" not in b
    assert a.count("## Session") == 1
    assert not os.path.exists(common.history_path(cwd, cfg)), "shared history.md was written"


def test_session_id_cannot_escape_history_dir(tmp_path):
    cwd = str(tmp_path)
    p = common.history_path(cwd, load_config(cwd), "../../etc/passwd")
    assert os.path.dirname(p).endswith("history") and ".." not in os.path.basename(p)
