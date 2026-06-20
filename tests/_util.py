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


def _run_hook(module_name, cwd, transcript_path, session_id):
    import importlib

    mod = importlib.import_module(module_name)
    saved = sys.stdin
    sys.stdin = io.StringIO(json.dumps({
        "cwd": cwd,
        "transcript_path": transcript_path,
        "session_id": session_id,
    }))
    try:
        mod.main()
    finally:
        sys.stdin = saved


def run_capture(cwd, transcript_path, session_id):
    """Invoke capture.main() with a simulated hook stdin payload."""
    _run_hook("capture", cwd, transcript_path, session_id)


def run_session_end(cwd, transcript_path, session_id):
    """Invoke session_end.main() with a simulated hook stdin payload."""
    _run_hook("session_end", cwd, transcript_path, session_id)
