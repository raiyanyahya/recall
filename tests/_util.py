"""Shared test helpers: build synthetic transcripts and drive the capture hook."""

import io
import json
import sys


def make_jsonl(path, objs):
    with open(path, "w", encoding="utf-8") as fh:
        for obj in objs:
            fh.write(json.dumps(obj) + "\n")


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def assistant(text, tools=None):
    content = [{"type": "text", "text": text}]
    for name, inp in tools or []:
        content.append({"type": "tool_use", "name": name, "input": inp})
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


def run_capture(cwd, transcript_path, session_id):
    """Invoke capture.main() with a simulated hook stdin payload."""
    import capture

    saved = sys.stdin
    sys.stdin = io.StringIO(json.dumps({
        "cwd": cwd,
        "transcript_path": transcript_path,
        "session_id": session_id,
    }))
    try:
        capture.main()
    finally:
        sys.stdin = saved
