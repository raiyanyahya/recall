"""Shared stdlib-only helpers: stdin parsing, paths, git, transcript location,
capture-offset state. Hooks depend only on this + config, so they never need a
third-party package and can never crash a session.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def read_hook_input():
    """Parse the JSON Claude Code passes a hook on stdin. Never raises."""
    try:
        if sys.stdin and not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                return json.loads(raw)
    except (OSError, ValueError):
        pass
    return {}


def output_dir(cwd, cfg):
    """Resolve the output dir, confined to within cwd.

    A project-local config is itself untrusted (it ships in the repo), so it must
    not be able to redirect writes outside the project via an absolute path or
    `..`. Anything that escapes cwd falls back to the default `.recall`.
    """
    requested = cfg.get("output_dir", ".recall") or ".recall"
    base = os.path.realpath(cwd)
    target = os.path.realpath(os.path.join(cwd, requested))
    if target == base or target.startswith(base + os.sep):
        return target
    return os.path.realpath(os.path.join(cwd, ".recall"))


def context_path(cwd, cfg):
    return os.path.join(output_dir(cwd, cfg), "context.md")


def history_path(cwd, cfg):
    return os.path.join(output_dir(cwd, cfg), "history.md")


def state_path(cwd, cfg):
    return os.path.join(output_dir(cwd, cfg), ".capture.json")


def pause_path(cwd, cfg):
    return os.path.join(output_dir(cwd, cfg), ".capture-paused")


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def ensure_output_dir(cwd, cfg):
    d = output_dir(cwd, cfg)
    os.makedirs(d, exist_ok=True)
    return d


def _open_nofollow(path, append):
    """Open for writing without following a symlink at the final path component.

    Prevents a pre-planted symlink (e.g. history.md -> /etc/something) from
    redirecting our writes. Raises OSError (ELOOP) if the target is a symlink.
    """
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return os.fdopen(os.open(path, flags, 0o644), "w", encoding="utf-8")


def write_text(path, data):
    with _open_nofollow(path, append=False) as fh:
        fh.write(data)


def append_text(path, data):
    with _open_nofollow(path, append=True) as fh:
        fh.write(data)


def load_state(cwd, cfg):
    try:
        with open(state_path(cwd, cfg), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(cwd, cfg, state):
    try:
        ensure_output_dir(cwd, cfg)
        write_text(state_path(cwd, cfg), json.dumps(state))
    except OSError:
        pass


def project_name(cwd):
    return os.path.basename(os.path.normpath(cwd)) or cwd


# Recall runs git inside the user's project, which may be an untrusted clone. A
# repo's own config can hijack plain git commands to run arbitrary code
# (core.fsmonitor, diff.external, hooks, a pager). Neutralize those vectors on
# every invocation; we only ever read, never prompt or fetch.
_GIT_HARDENING = [
    "-c", "core.fsmonitor=",
    "-c", "diff.external=",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.pager=cat",
]
_GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat", "PAGER": "cat"}


def _git(cwd, args):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "--no-pager", *_GIT_HARDENING, *args],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, **_GIT_ENV},
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _is_git_repo(cwd):
    return _git(cwd, ["rev-parse", "--is-inside-work-tree"]) == "true"


def git_info(cwd):
    if not _is_git_repo(cwd):
        return ""
    parts = []
    stat = _git(cwd, ["diff", "--no-ext-diff", "--stat"])
    if stat:
        parts.append("Uncommitted changes (git diff --stat):\n" + stat)
    log = _git(cwd, ["log", "--oneline", "-8"])
    if log:
        parts.append("Recent commits:\n" + log)
    return "\n\n".join(parts)


def git_uncommitted(cwd):
    """List of paths with uncommitted changes (porcelain), or []."""
    if not _is_git_repo(cwd):
        return []
    out, seen = [], set()
    for line in _git(cwd, ["status", "--porcelain"]).splitlines():
        path = line[3:].strip()  # "XY <path>"
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def project_transcripts(cwd):
    """All transcript paths for THIS project, newest first. Empty if none."""
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        return []
    for name in _candidates(cwd):
        cand = projects / name
        if cand.is_dir():
            try:
                files = sorted(cand.glob("*.jsonl"),
                               key=lambda f: f.stat().st_mtime, reverse=True)
            except OSError:
                return []
            return [str(f) for f in files]
    return []


def _candidates(cwd):
    variants = [
        cwd.replace("/", "-"),
        cwd.replace("/", "-").replace(".", "-").replace("_", "-"),
    ]
    seen, out = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def locate_transcript(cwd):
    """Find the current session transcript when a hook didn't provide one."""
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        return None
    for name in _candidates(cwd):
        cand = projects / name
        if cand.is_dir():
            newest = _newest_jsonl([cand])
            if newest:
                return newest
    # No directory matches THIS project. Do not fall back to scanning every
    # project's transcripts — that could summarize an unrelated project's
    # session into this project's files. Hooks pass transcript_path explicitly
    # anyway; only the /recall:save fallback reaches here.
    return None


def _newest_jsonl(dirs):
    newest, newest_m = None, -1.0
    for d in dirs:
        try:
            for f in d.glob("*.jsonl"):
                m = f.stat().st_mtime
                if m > newest_m:
                    newest, newest_m = str(f), m
        except OSError:
            continue
    return newest
