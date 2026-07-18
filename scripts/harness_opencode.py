"""OpenCode adapter: session discovery + export JSON -> Recall events.

Recall's optional opencode integration (installed explicitly with
``install.py --opencode`` — the Claude Code path never imports this module).
It talks to opencode only through its public CLI surfaces (``opencode session
list``, ``opencode export <id>``), never its internal storage files, so an
opencode storage-format change can't silently corrupt capture. All
opencode-shape knowledge is isolated here, mirroring how parse_transcript.py
isolates the Claude Code transcript shape.

Events produced here are the same dict shape parse_transcript emits, with tool
names normalized to the Claude-style spelling ("bash" -> "Bash"), so every
downstream consumer (render_history, commands, touched_files, make_context)
works unchanged on either harness.

Stdlib-only and fully defensive: every failure returns an empty result so the
opencode shim can never crash or block a session.
"""

import json
import os
import subprocess

# opencode tool part -> the input key that best describes it, and the
# Claude-style name downstream consumers already understand.
_TOOL_ARG = {
    "edit": "filePath",
    "write": "filePath",
    "read": "filePath",
    "bash": "command",
    "grep": "pattern",
    "glob": "pattern",
    "task": "description",
    "webfetch": "url",
    "websearch": "query",
}
_CANON = {
    "edit": "Edit",
    "write": "Write",
    "read": "Read",
    "bash": "Bash",
    "grep": "Grep",
    "glob": "Glob",
    "task": "Task",
    "webfetch": "WebFetch",
    "websearch": "WebSearch",
}
_FILE_ARGS = ("filePath",)

# Recall's own commands — not user activity (mirrors parse_transcript's guard).
_RECALL_INTERNAL = ("make_context.py", "opencode_capture.py")

_LIST_TIMEOUT = 15
_EXPORT_TIMEOUT = 60
# Bound how many sessions collect_events() will export while hunting for one
# with a real user prompt.
_MAX_GOAL_PROBES = 10


def _run_opencode(args, timeout):
    """Run the opencode CLI with a static argv, returning stdout or ""."""
    try:
        out = subprocess.run(
            ["opencode", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _json(text):
    """Parse JSON from CLI output, tolerating stray log lines before it."""
    if not text:
        return None
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return None
    try:
        return json.loads(text[min(starts):])
    except ValueError:
        return None


def project_sessions(cwd):
    """Session ids for THIS project only (directory == cwd), newest first.

    `opencode session list` returns sessions across every project, so filtering
    here is what preserves Recall's scoped-transcript guarantee: another
    project's session is never captured or summarized into this one's files.
    """
    doc = _json(_run_opencode(
        ["session", "list", "--format", "json", "-n", "200"], _LIST_TIMEOUT))
    if not isinstance(doc, list):
        return []
    base = os.path.realpath(cwd)
    rows = []
    for row in doc:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        d = row.get("directory")
        if isinstance(d, str) and os.path.realpath(d) == base:
            rows.append(row)
    rows.sort(key=lambda r: r.get("updated") or 0, reverse=True)
    return [r["id"] for r in rows]


def export_events(session_id):
    """Events for one session via `opencode export`, or [] on any failure."""
    doc = _json(_run_opencode(["export", session_id], _EXPORT_TIMEOUT))
    return events_from_export(doc)


def events_from_export(doc):
    """opencode export document -> parse_transcript-shaped event dicts."""
    if not isinstance(doc, dict):
        return []
    messages = doc.get("messages")
    if not isinstance(messages, list):
        return []
    events = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        info = msg.get("info") if isinstance(msg.get("info"), dict) else {}
        role = info.get("role")
        if role not in ("user", "assistant"):
            continue
        parts = msg.get("parts") if isinstance(msg.get("parts"), list) else []
        texts, tools = [], []
        for part in parts:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                # synthetic text is injected by opencode (command expansion,
                # file mentions), not something the user or model said
                if part.get("synthetic"):
                    continue
                t = part.get("text")
                if isinstance(t, str) and t.strip():
                    texts.append(t.strip())
            elif ptype == "tool" and role == "assistant":
                ev = _tool_event(part)
                if any(m in ev["detail"] for m in _RECALL_INTERNAL):
                    continue  # don't record Recall's own save/capture commands
                tools.append(ev)
        text = "\n".join(texts).strip()
        if text:
            events.append({"role": role, "text": text,
                           "tool": "", "detail": "", "files": []})
        events.extend(tools)
    return events


def _tool_event(part):
    raw = part.get("tool") if isinstance(part.get("tool"), str) else "tool"
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    inp = state.get("input") if isinstance(state.get("input"), dict) else {}
    arg = _TOOL_ARG.get(raw)
    detail = ""
    if arg and isinstance(inp.get(arg), str):
        detail = inp[arg]
    else:
        for v in inp.values():
            if isinstance(v, str) and v.strip():
                detail = v
                break
    detail = " ".join(detail.split())[:160]
    files = []
    if arg in _FILE_ARGS and isinstance(inp.get(arg), str):
        files = [inp[arg]]
    return {"role": "tool", "text": "", "tool": _CANON.get(raw, raw),
            "detail": detail, "files": files}


def collect_events(cwd):
    """(session_id, events) for the newest session of this project whose events
    contain a real user prompt, falling back to the newest non-empty session.
    The opencode analogue of make_context._facts_events — a bare /recall-save
    session shouldn't produce an empty context.md when a real one exists."""
    import parse_transcript

    first = None
    for sid in project_sessions(cwd)[:_MAX_GOAL_PROBES]:
        events = export_events(sid)
        if not events:
            continue
        if first is None:
            first = (sid, events)
        if parse_transcript.first_user_goal(events):
            return sid, events
    return first or (None, [])
