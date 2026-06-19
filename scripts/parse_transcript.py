"""Claude Code transcript (.jsonl) -> structured events + markdown renderers.

All transcript-shape knowledge is isolated here, so a Claude Code format change
only touches this file. Stdlib-only.

An event is a dict:
  {"role": "user"|"assistant"|"tool", "text": str, "tool": str, "detail": str,
   "files": [paths]}
"""

import json

_TOOL_ARG = {
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "Write": "file_path",
    "Read": "file_path",
    "NotebookEdit": "notebook_path",
    "Bash": "command",
    "Grep": "pattern",
    "Glob": "pattern",
    "Task": "description",
    "WebFetch": "url",
    "WebSearch": "query",
}
_FILE_ARGS = ("file_path", "notebook_path")


def _block_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def _tool_event(block):
    name = block.get("name", "tool")
    inp = block.get("input") or {}
    arg = _TOOL_ARG.get(name)
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
    return {"role": "tool", "text": "", "tool": name, "detail": detail, "files": files}


def parse_lines(lines):
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        etype = obj.get("type")
        content = (obj.get("message") or {}).get("content")

        if etype == "user":
            text = _block_text(content).strip()
            if text:  # skip tool_result-only turns
                events.append({"role": "user", "text": text,
                               "tool": "", "detail": "", "files": []})
        elif etype == "assistant":
            text = _block_text(content).strip()
            if text:
                events.append({"role": "assistant", "text": text,
                               "tool": "", "detail": "", "files": []})
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        events.append(_tool_event(block))
    return events


def parse(transcript_path):
    try:
        with open(transcript_path, "r", encoding="utf-8") as fh:
            return parse_lines(fh)
    except OSError:
        return []


def render_history(events):
    """Human-readable running-log lines for history.md."""
    out = []
    for ev in events:
        if ev["role"] == "user":
            out.append(f"\n**You:** {ev['text']}")
        elif ev["role"] == "assistant":
            out.append(f"\n**Claude:** {ev['text']}")
        else:
            label = f"{ev['tool']}: {ev['detail']}".rstrip(": ").strip()
            out.append(f"  - `{label}`")
    return "\n".join(out)


def prose(events, max_chars):
    """Concatenated user+assistant text (no tool noise) for the summarizer,
    keeping the most recent within the cap."""
    chunks = [ev["text"] for ev in events if ev["role"] in ("user", "assistant") and ev["text"]]
    text = "\n".join(chunks)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def touched_files(events):
    out, seen = [], set()
    for ev in events:
        for f in ev.get("files", []):
            if f and f not in seen:
                seen.add(f)
                out.append(f)
    return out


def commands(events):
    out, seen = [], set()
    for ev in events:
        if ev["role"] == "tool" and ev["tool"] == "Bash" and ev["detail"]:
            if ev["detail"] not in seen:
                seen.add(ev["detail"])
                out.append(ev["detail"])
    return out


def first_user_goal(events):
    for ev in events:
        if ev["role"] == "user" and ev["text"]:
            return " ".join(ev["text"].split())
    return ""


def last_assistant_state(events):
    for ev in reversed(events):
        if ev["role"] == "assistant" and ev["text"]:
            return " ".join(ev["text"].split())
    return ""
