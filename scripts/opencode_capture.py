#!/usr/bin/env python3
"""OpenCode capture: append new session activity to .recall/history.md.

Invoked by the opencode plugin shim (integrations/opencode/recall.ts) on every
`session.idle` — the opencode analogue of the Claude Code Stop hook, which this
file mirrors (capture.py). The session is read through `opencode export`
(public CLI, never opencode's internal storage), and we track how many events
were already captured per session in .capture.json (keyed "oc:<session id>",
which can't collide with the Claude hooks' byte-offset entries) so repeated
idles only append what's new.

Same guarantees as capture.py: stdlib-only, fully defensive (any error exits
0 so a session is never affected), honors capture_history / .capture-paused,
redacts before writing. If auto_save_context is "on_end", context.md is also
regenerated — on every idle, since opencode has no end-of-session hook.
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def capture_session(cwd, session_id):
    import harness_opencode
    import parse_transcript
    from common import (
        append_text,
        ensure_output_dir,
        history_path,
        load_state,
        pause_path,
        project_name,
        save_state,
    )
    from config import load_config
    from redact import redact

    cfg = load_config(cwd)

    if not cfg.get("capture_history", True):
        return
    pp = pause_path(cwd, cfg)
    if pp is None:
        return  # output dir escapes the project; refuse to write anywhere
    if os.path.exists(pp):
        return  # user paused logging for this project

    events = harness_opencode.export_events(session_id)
    if not events:
        return

    # Incremental by EVENT COUNT (the export is a full document, not an
    # append-only file, so byte offsets don't apply). Messages only ever append
    # within a session, so events[start:] is exactly what's new.
    key = "oc:" + session_id
    state = load_state(cwd, cfg)
    try:
        start = int(state.get(key, 0) or 0)
    except (TypeError, ValueError):
        start = 0  # corrupted/tampered .capture.json entry; re-capture this session
    if start > len(events):
        start = 0  # session shrank (revert/undo); re-capture from the top

    new = events[start:]
    if new:
        ensure_output_dir(cwd, cfg)
        hist = history_path(cwd, cfg)
        prefix = ""
        if not os.path.exists(hist):
            prefix += f"# Recall History — {project_name(cwd)}\n"
        if start == 0:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            prefix += f"\n\n## Session {session_id[:8]} — {stamp} (opencode)\n"
        body = parse_transcript.render_history(new)
        if cfg.get("redact", True):
            body = redact(body)
        append_text(hist, prefix + body + "\n")

    # Re-insert at the end so this active session is the most-recent entry and
    # save_state's session cap never prunes it.
    state.pop(key, None)
    state[key] = len(events)
    save_state(cwd, cfg, state)

    if cfg.get("auto_save_context", "off") == "on_end":
        import make_context
        make_context.run(cwd, quiet=True, harness="opencode")


def main():
    ap = argparse.ArgumentParser(description="Recall: capture an opencode session")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--session", required=True)
    args = ap.parse_args()
    capture_session(args.cwd, args.session)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
