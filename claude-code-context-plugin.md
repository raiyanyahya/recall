# Project Plan: Continuum — A Context-Memory Plugin for Claude Code

> **One-liner:** A Claude Code plugin that gives every project a durable memory. A local Python summarizer keeps a single, always-current `context.md` (overwritten with the latest high-quality summary of the work) and an append-only `history.md` (the full running log of changes, decisions, and thoughts). On a new session, the plugin offers the summary so Claude starts already knowing the goal, what's been done, and what's next — instead of you re-explaining and burning tokens.

- **Status:** Planning
- **Owner:** Raiyan Yahya
- **Created:** 2026-06-16
- **Category:** Developer Tooling / Claude Code Plugin / LLM
- **Codename:** `continuum`

---

## 1. The Problem & The Idea

Claude Code sessions are stateless across restarts. Every new session you re-explain the project — what you're building, what's already done, what the current blocker is — which wastes tokens and your time, and Claude still lacks the nuance of prior sessions. `CLAUDE.md` helps with *static* project facts, but it's hand-maintained and doesn't capture *what just happened* or *where we left off*.

**Continuum** closes that loop automatically:

1. A **local Python summarizer** reads the session transcript and produces a high-quality, structured summary.
2. It **overwrites `context.md`** — a single file that is always the *latest* state (goal, progress, decisions, current state, next steps, open questions).
3. It **appends to `history.md`** — an append-only journal so nothing is ever lost (every update, decision, and thought, timestamped).
4. On a **new session**, the plugin surfaces `context.md` so Claude (and you) resume with full context.
5. You stay in control of **when** the summary updates — via an explicit command and/or an opt-in auto-save.

**Why two files (the key data-model decision):**
- `context.md` = *state*. Always current, overwritten, small, cheap to load every session. Answers "where are we **right now**?"
- `history.md` = *log*. Append-only, never overwritten, the durable record. Answers "how did we **get** here?" and protects against the summarizer ever dropping something important.

---

## 2. Hard Constraints (verified against Claude Code internals)

These shaped the whole design — the naive version of this idea isn't buildable as-imagined:

- **Hooks are NOT interactive.** A hook cannot open a yes/no prompt, read from the terminal, or block for a keystroke. It communicates only via **exit codes**, **stderr**, and **JSON on stdout** (`additionalContext`, `systemMessage`, etc.). → So "ask me if I want to load/update the summary" can't be a literal hook dialog. We achieve "asking" two ways: (a) the SessionStart hook injects an instruction that makes *Claude* ask you in chat (real interactive UX), and (b) a **slash command** you run when you decide to save.
- **`SessionStart` can inject context.** On exit 0 it adds its stdout (or a JSON `additionalContext` field) to the model's context at session start. Matcher sources: `startup`, `resume`, `clear`, `compact`. It receives `session_id`, `cwd`, and `transcript_path` on stdin. → This is exactly how we load `context.md` into a fresh session.
- **`SessionEnd` can read the transcript but can't inject.** It receives `transcript_path`; its exit code is ignored (the session is ending). → Perfect for *writing* the summary, useless for *asking*.
- **`Stop` fires when Claude finishes a response.** Gets `session_id` (reconstruct transcript path from it). Can inject `additionalContext`/`systemMessage`. → Used for an optional non-intrusive "consider saving context" nudge.
- **Transcript format is JSONL** at `~/.claude/projects/<project-hash>/<session-id>.jsonl` — one JSON object per line (messages, tool_use, etc.). → A Python script can parse it directly to build the summary input.
- **Plugins bundle hooks + commands + scripts.** Layout: `.claude-plugin/plugin.json` (manifest) + `hooks/hooks.json` + `commands/` (slash commands) + a `scripts/`/`bin/` dir for the Python summarizer. Distributable via a plugin marketplace or `--plugin-dir` for local dev.

---

## 3. Architecture

```
                          NEW SESSION                         SESSION END / ON DEMAND
                              │                                        │
                     ┌────────▼─────────┐                    ┌─────────▼──────────┐
   hooks.json ──────▶│ SessionStart hook │                   │ SessionEnd hook    │
                     │ (matcher: startup,│                   │  OR  /continuum:save│
                     │  resume, clear)   │                   │ (slash command)    │
                     └────────┬─────────┘                    └─────────┬──────────┘
                              │ reads                                   │ passes transcript_path
                              ▼                                         ▼
                      ┌───────────────┐                        ┌──────────────────┐
                      │  context.md   │◀───────overwrite───────│  summarize.py     │
                      │ (latest state)│                        │ (local Python)    │
                      └───────────────┘                        │  1. parse JSONL   │
                              │ injected as                    │  2. + prev context│
                              │ additionalContext              │  3. call backend  │
                              ▼                                 │  4. write files   │
                      Claude starts the                        └────────┬──────────┘
                      session already knowing                           │ append
                      goal / progress / next steps                      ▼
                                                              ┌──────────────────┐
                                          backend:            │   history.md     │
                                    Ollama (local)  OR        │ (append-only log)│
                                    Claude API (Haiku/Sonnet) └──────────────────┘
```

### Plugin file layout
```
continuum/
├── .claude-plugin/
│   └── plugin.json              # manifest (name, description, version)
├── hooks/
│   └── hooks.json               # SessionStart, SessionEnd, (optional) Stop
├── commands/
│   ├── save.md                  # /continuum:save  — summarize now, overwrite context.md
│   ├── show.md                  # /continuum:show  — print current context.md
│   └── load.md                  # /continuum:load  — re-inject context.md mid-session
├── scripts/
│   ├── summarize.py             # the local summarizer (core)
│   ├── parse_transcript.py      # JSONL → cleaned event list
│   ├── session_start.sh         # reads context.md, emits additionalContext JSON
│   └── backends/
│       ├── ollama.py            # local model backend (default)
│       └── claude.py            # Claude API backend (optional, higher quality)
├── continuum.config.json        # per-project config (backend, model, auto-save, redaction)
└── README.md
```

### Files written **into the user's project** (committable, the actual deliverable)
- `.continuum/context.md` — overwritten each save (latest summary).
- `.continuum/history.md` — appended each save (chronological journal).
- (Configurable path; default a `.continuum/` dir so it's tidy and git-ignorable or committable per preference.)

---

## 4. How Each Behavior Maps to a Real Mechanism

| Your requirement | Mechanism |
|---|---|
| "Summarizes context every time, updates a local `context.md`" | `summarize.py` overwrites `context.md` on save (SessionEnd auto-save and/or `/continuum:save`). |
| "Keeps the latest summary intact" | `context.md` is **overwritten** with the freshest summary; never appended. |
| "Ask during a session if the summary should be updated" | (a) `/continuum:save` — you decide and run it. (b) Optional `Stop` hook nudge: after N responses or when a meaningful git diff exists, inject a `systemMessage`: *"💡 Run `/continuum:save` to update the project summary."* (non-blocking, non-interactive). |
| "Asks at the start of a new session if the local summary should be considered" | `SessionStart` hook injects `additionalContext` containing the summary **plus** an instruction: *"A saved project summary exists (below). Briefly confirm with the user whether to use it before relying on it."* → Claude asks **you** in chat — real interactive confirmation, within the hook's constraints. A config flag `auto_load: true` skips the asking and just loads it. |
| "`history.md` containing all changes/updates/thoughts, appending" | Every save appends a timestamped, structured entry to `history.md`. Never overwritten. |
| "Useful in the next session — goal, what we did, etc." | Summary schema (below) is explicitly designed for resumption. |
| "Local Python high-quality summarizer" | `summarize.py` with a pluggable backend; **Ollama (local) is the default**, Claude API optional. |

---

## 5. The Summarizer (`summarize.py`)

**Input pipeline:**
1. Receive `transcript_path` (from hook stdin JSON, or reconstruct from `session_id`).
2. **Parse JSONL** → keep user prompts, assistant text, and salient tool activity (file edits, commands, decisions); drop noise (raw file dumps, huge tool outputs) to control token cost.
3. **Read existing `context.md`** (if present) for **incremental** summarization — feed *previous summary + this session's delta* instead of re-summarizing everything. This keeps quality high and tokens low.
4. **Optionally pull `git diff --stat` / recent commits** for ground-truth on what changed.

**Output schema (`context.md`)** — designed for next-session resumption:
```markdown
# Project Context — <project> (updated <timestamp>)

## 🎯 Goal
What we're ultimately building / the objective.

## ✅ Done
Concrete things completed (with file refs where useful).

## 🚧 Current State
Where things stand right now; what's in-progress / half-done.

## 🧭 Next Steps
The immediate actionable next tasks.

## 🧠 Key Decisions
Choices made and *why* (so they aren't relitigated).

## ❓ Open Questions / Blockers
Unresolved items needing the user or more work.

## 📂 Key Files
Files central to the work + one-line purpose each.
```

**`history.md` entry (appended):**
```markdown
---
## <timestamp> — session <id-short>
**Summary of this session:** <2-4 sentences>
**Changes:** <bullets — features, fixes, refactors>
**Decisions/Thoughts:** <bullets>
**Files touched:** <list>
```

**Quality measures:** structured prompt with the schema above; few-shot example; instruction to be specific and reference files; incremental merge (preserve still-true items from prior `context.md`, update changed ones, don't hallucinate completion). Idempotent and safe to run repeatedly.

---

## 6. Summarizer Backend — the Key Decision

The user said "local Python summarizer." Two viable backends; ship both, default to local.

### Backend A — **Ollama (local), default** *(dovetails with the `ollama-box` project)*
- **Pros:** fully private (transcript never leaves the machine — important, transcripts contain code/secrets), zero marginal cost, no API key, works offline.
- **Cons:** summary quality depends on the local model + hardware; needs Ollama running (the `ollama-box` container from the first project is a natural fit here).
- **Model suggestion:** an instruction-tuned 7–8B (e.g. `qwen2.5:7b`, `llama3.1:8b`) — strong enough for summarization; larger if hardware allows.

### Backend B — **Claude API (optional), highest quality**
- **Pros:** best summary quality and instruction-following; trivial to run.
- **Cons:** costs money; sends transcript to an API (mitigate with redaction + opt-in); needs network + key.
- **Model + cost (current pricing):**

| Model | ID | Input $/MTok | Output $/MTok | Fit |
|---|---|---|---|---|
| **Claude Haiku 4.5** | `claude-haiku-4-5` | $1 | $5 | **Cheap + high-quality — recommended for summarization** |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | $3 | $15 | When you want max nuance |

- **Worked cost (Haiku):** a ~100K-token session transcript summarized to ~1.5K tokens ≈ **$0.10 input + ~$0.008 output ≈ ~$0.11 per save**. With **incremental** summarization (prev summary + only the new delta, not the whole transcript) and **prompt caching** of the stable parts, typical updates land at **1–3¢**. Sonnet ≈ 3×.
- **Net token economics either way:** loading a ~1.5K-token `context.md` at session start is far cheaper than the multi-thousand-token back-and-forth of re-explaining the project — and the summary itself is generated out-of-band, not in your interactive session.

**Recommendation:** default **Ollama** (privacy + zero cost + ties to the other project); offer **Claude Haiku** as a one-line config switch for users who want top quality and don't mind the cents. Backend is selected in `continuum.config.json`.

---

## 7. Configuration (`continuum.config.json`)

| Key | Default | Purpose |
|---|---|---|
| `backend` | `"ollama"` | `"ollama"` or `"claude"`. |
| `model` | `"qwen2.5:7b"` | Backend model id (`claude-haiku-4-5` for Claude). |
| `output_dir` | `".continuum"` | Where `context.md` / `history.md` live. |
| `auto_save` | `"prompt"` | `"off"` \| `"prompt"` (nudge via Stop hook) \| `"on_session_end"` (auto-write). |
| `auto_load` | `false` | `true` = inject context silently; `false` = have Claude ask first. |
| `redact` | `true` | Strip obvious secrets (`.env` values, keys, tokens) before sending to any backend. |
| `max_input_tokens` | `60000` | Cap transcript tokens fed to the summarizer (truncate oldest, keep recent + prev summary). |
| `include_git` | `true` | Add `git diff --stat` + recent commits as ground truth. |

---

## 8. Privacy & Safety

- **Transcripts are sensitive** (code, paths, possibly secrets). Default backend is **local** for this reason.
- **Redaction pass** before any backend call (regex for common secret shapes, `.env` contents, auth headers); on by default.
- **Claude backend is explicit opt-in**, with a clear note that the (redacted) transcript leaves the machine.
- **No network in the default path.** The plugin must work fully offline with Ollama.
- Hooks run with the user's permissions — scripts are minimal, read transcript + project files only, write only under `output_dir`.

---

## 9. Risks & Tradeoffs

| Risk | Mitigation |
|---|---|
| Hooks can't truly prompt → "ask me" feels different than imagined | Use Claude-asks-in-chat (SessionStart instruction) + explicit `/continuum:save`; document the model clearly. |
| Summarizer drops something important (overwrite is lossy) | `history.md` is append-only and never overwritten — the durable backstop. |
| Local model quality too low | Configurable model; Claude Haiku fallback; structured schema + few-shot to lift quality. |
| Injecting `context.md` every session costs tokens | Keep it tight (~1–2K tokens); still far cheaper than re-explaining; `auto_load` lets users opt out. |
| Secrets leaking to an API backend | Local default + redaction + opt-in Claude backend with explicit warning. |
| Transcript path/format changes across Claude Code versions | Isolate parsing in `parse_transcript.py`; prefer hook-provided `transcript_path` over reconstruction; pin tested versions. |
| SessionEnd auto-save runs on every tiny session | Config `auto_save`; skip when transcript below a min length or no git changes. |

---

## 10. Roadmap

**Phase 0 — Spike (½–1 day):** Minimal plugin: `SessionStart` hook that injects a hand-written `context.md`. Prove injection works and Claude resumes with it.

**Phase 1 — Summarizer + files (2–3 days):** `parse_transcript.py` + `summarize.py` with the Ollama backend; write `context.md` (overwrite) and `history.md` (append) with the schemas above. Wire `/continuum:save`.

**Phase 2 — Lifecycle + asking (1–2 days):** `SessionStart` injects real `context.md` + the "confirm with user" instruction; `auto_load` flag; optional `SessionEnd` auto-save; `Stop`-hook nudge for `auto_save: "prompt"`.

**Phase 3 — Backends + privacy (1–2 days):** Claude API backend (Haiku default) with prompt caching + incremental summarization; redaction pass; `continuum.config.json`.

**Phase 4 — Packaging (1 day):** Plugin manifest, README with GIF, marketplace/`--plugin-dir` install, sensible defaults, tests for the parser and schema.

**Definition of done:** Open a brand-new session on a project that's used Continuum → Claude greets you with the goal, what's done, and next steps (after a one-line confirm), `context.md` reflects the latest state, `history.md` has a complete journal, and you never had to re-explain the project. All offline by default.

---

## 11. Open Questions
1. **Default backend** — ship Ollama-default (privacy/cost, recommended) or Claude-Haiku-default (quality)? *(Lean: Ollama.)*
2. **`auto_save` default** — `"prompt"` (nudge) vs `"on_session_end"` (silent auto-write)? *(Lean: `"prompt"`.)*
3. **`auto_load` default** — ask-first vs load-silently at session start? *(Lean: ask-first for trust, flag to disable.)*
4. **Commit policy** — should `.continuum/` be git-committed (shareable team memory) or git-ignored (personal)? Document both.
5. **Scope** — per-project only, or also a global/user-level memory across all projects?
6. **Transcript fidelity** — how aggressively to filter tool noise vs. preserving detail for summary quality?

---

## 12. References
- Claude Code plugins: `code.claude.com/docs/en/plugins` and `plugins-reference`.
- Hooks (events, JSON I/O, exit codes): `code.claude.com/docs/en/hooks` and `hooks-guide`.
- Sessions / transcript format & location: `code.claude.com/docs/en/sessions`.
- Backends: Ollama HTTP API (see the `ollama-box` project plan); Claude API — `claude-haiku-4-5` ($1/$5 per MTok), `claude-sonnet-4-6` ($3/$15).
