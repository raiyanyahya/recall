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


def load_config(cwd):
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(cwd, CONFIG_FILENAME), "r", encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass  # missing/malformed -> defaults; never fail a hook over config
    return cfg
