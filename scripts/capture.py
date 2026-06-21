#!/usr/bin/env python3
"""Stop / SessionEnd hook: append new session activity to .recall/history.md.

history.md is the append-only running log of everything done. We track how many
transcript lines we've already captured per session (in .recall/.capture.json)
so repeated Stop fires only append what's new.

Stdlib-only and fully defensive: any error exits 0 so a session is never affected.
Capture can be turned off via `capture_history: false` or a `.capture-paused`
marker file in the output dir.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def capture_session(data):
    """Append any new transcript activity to history.md. Takes the parsed hook
    payload so other hooks (e.g. SessionEnd) can reuse it."""
    import parse_transcript
    from common import (
        append_text,
        ensure_output_dir,
        history_path,
        load_state,
        locate_transcript,
        pause_path,
        project_name,
        save_state,
    )
    from config import load_config
    from redact import redact

    cwd = data.get("cwd") or os.getcwd()
    cfg = load_config(cwd)

    if not cfg.get("capture_history", True):
        return
    pp = pause_path(cwd, cfg)
    if pp is None:
        return  # output dir escapes the project; refuse to write anywhere
    if os.path.exists(pp):
        return  # user paused logging for this project

    transcript_path = data.get("transcript_path") or locate_transcript(cwd)
    if not transcript_path or not os.path.exists(transcript_path):
        return

    session_id = data.get("session_id", "") or "session"

    # Incremental by BYTE OFFSET so we only read what's new each turn (not the
    # whole transcript). state[session_id] is the offset processed so far.
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return

    state = load_state(cwd, cfg)
    start = int(state.get(session_id, 0) or 0)
    if start > size:
        start = 0  # transcript rotated/shrank; re-capture from the top

    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(start)
            chunk = fh.read()
    except OSError:
        return

    # Only process complete lines; a partial trailing line is still being
    # written and will be picked up on the next call.
    nl = chunk.rfind(b"\n")
    if nl == -1:
        return
    complete = chunk[:nl + 1]
    new_offset = start + len(complete)

    events = parse_transcript.parse_lines(
        complete.decode("utf-8", "replace").splitlines())
    if events:
        ensure_output_dir(cwd, cfg)
        hist = history_path(cwd, cfg)
        prefix = ""
        if not os.path.exists(hist):
            prefix += f"# Recall History — {project_name(cwd)}\n"
        if start == 0:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            prefix += f"\n\n## Session {session_id[:8]} — {stamp}\n"
        body = parse_transcript.render_history(events)
        if cfg.get("redact", True):
            body = redact(body)
        append_text(hist, prefix + body + "\n")

    state[session_id] = new_offset
    save_state(cwd, cfg, state)


def main():
    from common import read_hook_input
    capture_session(read_hook_input())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
