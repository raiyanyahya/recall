---
description: Show the local Recall history log (.recall/history.md)
allowed-tools: Bash, Read
---

Show the tail of `.recall/history.md` — the running local log of this and
prior sessions. If it's large, show the last ~120 lines:

```
tail -n 120 .recall/history.md
```

If the file doesn't exist, tell the user nothing has been logged yet (logging
starts once the plugin is active and is written as the session progresses).
