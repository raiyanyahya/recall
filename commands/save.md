---
description: Generate / overwrite .recall/context.md from the local history using the offline summarizer
allowed-tools: Bash
---

Generate (or overwrite) this project's `context.md` summary now, using Recall's
local offline summarizer.

Run with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/make_context.py" --cwd "$(pwd)"
```

Then report back:

- On success it prints the path it wrote and which summarizer path ran
  (numpy-accelerated TextRank if numpy is present, otherwise the pure-Python
  TextRank — both vendored, no install needed). Confirm the save and read back the
  **Goal** and **Where we left off** lines from `.recall/context.md`.
- If it errored, surface the exact message.
