---
description: Generate / overwrite .recall/context.md from the local history using the offline summarizer
allowed-tools: Bash
---

Generate (or overwrite) this project's `context.md` summary now, using Recall's
local offline summarizer.

Run with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/make_context.py" || python "${CLAUDE_PLUGIN_ROOT}/scripts/make_context.py"
```

(`make_context.py` defaults to the current directory, so no `--cwd` is needed —
and on Windows passing the shell's `$(pwd)` would hand it a `/c/...` path that
doesn't match the transcript dir. The `|| python` fallback covers Windows, where
the interpreter is normally `python`, not `python3`.)

Then report back:

- On success it prints the path it wrote and which summarizer path ran
  (numpy-accelerated TextRank if numpy is present, otherwise the pure-Python
  TextRank — both vendored, no install needed). Confirm the save and read back the
  **Goal** and **Where we left off** lines from `.recall/context.md`.
- If it errored, surface the exact message.
