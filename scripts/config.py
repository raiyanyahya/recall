"""Recall configuration.

Defaults live here so the plugin works with zero config. A per-project
``recall.config.json`` (in the project root) overrides any subset. The shipped
file doubles as a documented template.
"""

import json
import os

DEFAULTS = {
    # Directory (relative to project root) where history.md / context.md live.
    "output_dir": ".recall",
    # Append every session to history.md automatically (Stop / SessionEnd hooks).
    "capture_history": True,
    # Regenerate context.md automatically when a session ends, so memory stays
    # current without running /recall:save: "off" (default) | "on_end".
    "auto_save_context": "off",
    # How many sentences the extractive summarizer keeps for the Summary section.
    "summary_sentences": 8,
    # Strip obvious secrets before writing to the (committable) md files.
    "redact": True,
    # Include `git diff --stat` + recent commits as ground truth in context.md.
    "include_git": True,
    # Cap on characters fed to the summarizer (oldest history is dropped).
    "max_input_chars": 200000,
}

CONFIG_FILENAME = "recall.config.json"


def _coerce(user):
    """Overlay only known keys whose value matches the default's type onto the
    defaults. A committed recall.config.json is untrusted input, so a wrong-typed
    value (output_dir as a number, summary_sentences as a string, a negative
    char cap, …) must fall back to the default rather than crash a hook or the
    summarizer."""
    cfg = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in user:
            continue
        value = user[key]
        if isinstance(default, bool):        # bool first: bool is a subclass of int
            if isinstance(value, bool):
                cfg[key] = value
        elif isinstance(default, int):
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                cfg[key] = value
        elif isinstance(default, str):
            if isinstance(value, str) and value:
                cfg[key] = value
    return cfg


def load_config(cwd):
    try:
        with open(os.path.join(cwd, CONFIG_FILENAME), "r", encoding="utf-8") as fh:
            user = json.load(fh)
    except (OSError, ValueError):
        return dict(DEFAULTS)  # missing/malformed -> defaults; never fail over config
    return _coerce(user) if isinstance(user, dict) else dict(DEFAULTS)
