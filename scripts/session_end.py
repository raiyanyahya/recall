#!/usr/bin/env python3
"""SessionEnd hook: flush the final activity to history.md, then — if
`auto_save_context` is "on_end" — regenerate context.md so the project memory
stays current without anyone having to run /recall:save.

The summary is a local algorithm, so this costs no model tokens. Stdlib-only for
the capture step; make_context is only imported when auto-save is enabled.
Defensive: any error exits 0 so a session is never affected.
"""

import os
import sys

# Force UTF-8 stdout so non-ASCII never raises UnicodeEncodeError on Windows
# (default cp1252), where the bare except below would swallow it silently.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import capture
    from common import read_hook_input
    from config import load_config

    data = read_hook_input()
    capture.capture_session(data)  # log any remaining turns

    cwd = data.get("cwd") or os.getcwd()
    cfg = load_config(cwd)
    if cfg.get("auto_save_context", "off") == "on_end":
        import make_context
        make_context.run(cwd, data.get("transcript_path"), quiet=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
