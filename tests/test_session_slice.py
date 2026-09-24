"""The legacy shared history.md is sliced to ONE session's block.

Only the fallback path reads it now (sessions log to history/<id8>.md), but a
project captured before that change still has the shared file, and summarizing all
of it mixed unrelated older sessions into the one being saved.
"""

from make_context import _session_slice

HISTORY = """# Recall History - Example Project

## Session aaaaaaaa - 2026-09-15 10:00
**You:** rename the widget
**Claude:** OLD_SESSION_MARKER renamed it.

## Session bbbbbbbb - 2026-09-22 15:39
**You:** add a column to the report
**Claude:** NEW_SESSION_MARKER shipped it.
"""


def test_named_session_wins():
    got = _session_slice(HISTORY, "/x/y/bbbbbbbb-1234-5678.jsonl")
    assert "NEW_SESSION_MARKER" in got
    assert "OLD_SESSION_MARKER" not in got


def test_unknown_id_falls_back_to_last_block():
    got = _session_slice(HISTORY, "/x/y/cccccccc-0000.jsonl")
    assert "NEW_SESSION_MARKER" in got
    assert "OLD_SESSION_MARKER" not in got


def test_earlier_session_still_reachable():
    # A parallel session appending after this one must not steal the slice.
    assert "OLD_SESSION_MARKER" in _session_slice(HISTORY, "/x/y/aaaaaaaa-9999.jsonl")


def test_history_without_headers_passes_through():
    text = "just prose, no headers"
    assert _session_slice(text, "/x/y/bbbbbbbb.jsonl") == text


def test_missing_transcript_path_still_scopes():
    assert "OLD_SESSION_MARKER" not in _session_slice(HISTORY, "")
