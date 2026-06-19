# Recall — fully-local project memory for Claude Code

[![CI](https://github.com/raiyanyahya/recall/actions/workflows/ci.yml/badge.svg)](https://github.com/raiyanyahya/recall/actions/workflows/ci.yml)
[![CodeQL](https://github.com/raiyanyahya/recall/actions/workflows/codeql.yml/badge.svg)](https://github.com/raiyanyahya/recall/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Claude Code starts every session cold. Recall keeps a local log of your
> sessions and condenses it into a resume-ready summary — **entirely on your
> machine**. No API key, no external model, nothing sent anywhere. It's built for
> people running Claude Code locally on a subscription: the only AI in the loop is
> Claude Code itself; the summarization is done by a classical Python summarizer.

## Why Recall

- **Free on your subscription.** It solves the cold-start problem — no more
  re-explaining the project each session — without a metered summarizer running up
  a bill. The summary is a local algorithm, not an LLM call, so persistent memory
  costs you nothing beyond the subscription you already pay for.
- **Nothing leaves your machine.** Your transcripts (code, paths, sometimes
  secrets) are never sent to any API. Most "memory" tools pipe your context to a
  model endpoint; Recall makes a privacy guarantee they can't.
- **Zero-friction.** No `pip install`, no local model to run, no key to configure,
  works offline. It starts working the moment the plugin loads.

Two files, written into your project under `.recall/`:

- **`history.md`** — *the log.* Append-only. Every session is captured here as it
  happens (your prompts, Claude's replies, the files touched and commands run).
- **`context.md`** — *the summary.* Overwritten on demand by the local summarizer
  — the condensed "where are we right now" you load into the next session.

## How it works

| Moment | What happens |
|---|---|
| **During the session** | The `Stop` / `SessionEnd` hooks append new activity to `.recall/history.md`. Capture is incremental (only new turns) and fully local. |
| **At session start** | The `SessionStart` hook surfaces `context.md` and has Claude ask you two things: resume from the saved context? and keep logging this session? |
| **Before you wrap up** | You run `/recall:save`. The **local summarizer** reads `history.md` and (over)writes `context.md`. |

There is no LLM call anywhere — the summary is produced by **TF-IDF + TextRank**
(extractive summarization) running locally.

## The summarizer

`scripts/summarizer.py` ranks the most central sentences of your session:

1. TF-IDF sentence vectors
2. a cosine-similarity graph between sentences
3. **TextRank** — PageRank power iteration over that graph — to score sentences
4. the top *N* are kept in original order

`context.md` wraps that summary with deterministic facts pulled straight from the
transcript and git: the goal (your first ask), files touched, commands run, where
you left off, and `git diff --stat`.

**No installs required.** The whole TF-IDF + TextRank implementation is vendored
in `summarizer.py`. If `numpy` happens to be importable it's used to vectorize the
math (faster on big sessions); if not, an identical pure-Python TextRank runs
instead. Same algorithm, same result — numpy is an optional accelerator, never a
requirement. The save output tells you which path ran.

## Commands

- `/recall:save` — run the local summarizer → (over)write `context.md`.
- `/recall:show` — print `context.md`.
- `/recall:log` — tail `history.md`.

## Configuration — `recall.config.json`

Drop this in your project root to override defaults:

| Key | Default | Purpose |
|---|---|---|
| `output_dir` | `".recall"` | Where `history.md` / `context.md` live. |
| `capture_history` | `true` | Append session activity to `history.md`. |
| `summary_sentences` | `8` | How many sentences the summary keeps. |
| `redact` | `true` | Strip obvious secrets before writing the md files. |
| `include_git` | `true` | Add `git diff --stat` + recent commits to `context.md`. |
| `max_input_chars` | `200000` | Cap on text fed to the summarizer (oldest dropped). |

**Pause logging** for a project without editing config: create
`.recall/.capture-paused`. Delete it to resume.

## Privacy & security

Recall makes **no network calls, uses no API key, and loads no third-party
model.** The summarizer is local Python; the hooks are stdlib-only (numpy is an
optional accelerator). It reads your session transcript and writes only under
`output_dir`. Concretely:

- **No credentials, ever.** The plugin has zero references to API keys, auth,
  `ANTHROPIC_*`, or HTTP. If `claude` itself shows *"Invalid API key"*, that's the
  CLI's own auth — usually a stale `ANTHROPIC_API_KEY` env var shadowing your
  subscription login. `unset ANTHROPIC_API_KEY` (or run `env -u ANTHROPIC_API_KEY
  claude …`). It has nothing to do with Recall.
- **Redaction.** A best-effort pass strips common secret shapes (API keys, tokens,
  `.env` assignments, PEM keys) before writing, since `context.md` / `history.md`
  may be committed. Best-effort, not a guarantee — review before committing.
- **Hardened git.** `git diff`/`log` are run with `core.fsmonitor`,
  `diff.external`, hooks, and the pager disabled, so an untrusted cloned repo
  can't use its own git config to execute code when Recall reads ground-truth.
  Set `include_git: false` to skip git entirely.
- **Confined writes.** `output_dir` is forced to stay inside the project; a
  project-shipped config can't redirect writes to an absolute path or `../..`.
- **Scoped transcript.** Recall only reads the transcript for the current
  project (matched by cwd); it never falls back to another project's sessions.
- **Trust boundary for shared memory.** `context.md` is injected into the model at
  session start. If you **commit `.recall/` as shared team memory**, treat it
  like any other shared input: a teammate (or a bad actor with repo write access)
  could craft a `context.md` to attempt prompt-injection. SessionStart fences the
  content and labels it untrusted data, and Claude asks before relying on it — but
  if you don't fully trust who can write the repo, keep `.recall/` git-ignored
  (the default).

## Committing `.recall/`

Both are fine. Commit it for shared team memory, or git-ignore it for personal
memory (`.gitignore` ships ignoring it by default — flip the comment to commit).

## Install

**From the marketplace** (this repo is its own marketplace):

```
/plugin marketplace add raiyanyahya/recall
/plugin install recall@recall
```

**Local dev** (no install step):

```
claude --plugin-dir /path/to/recall
```

No `pip install` — the summarizer is vendored and stdlib-only (numpy used as an
optional accelerator if present). Work a session, run `/recall:save`, and open
a fresh session — Recall greets you with where you left off.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install pytest ruff bandit numpy   # numpy optional

ruff check scripts tests               # lint
bandit -c pyproject.toml -r scripts    # security static analysis
pytest                                 # run the suite (also test without numpy)
claude plugin validate .               # official manifest validation
```

CI (`.github/workflows/`) runs lint + Bandit, the test suite across Python
3.9–3.13 **with and without numpy** (both summarizer paths), CodeQL, secret
scanning, and manifest JSON validation on every push and PR. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Layout

```
recall/
├── .claude-plugin/plugin.json   # manifest
├── hooks/hooks.json             # SessionStart (ask/resume) · Stop+SessionEnd (capture)
├── commands/                    # /recall:save · show · log
├── scripts/
│   ├── summarizer.py            # vendored TF-IDF + TextRank (numpy optional)
│   ├── make_context.py          # build/overwrite context.md
│   ├── capture.py               # append session activity to history.md
│   ├── session_start.py         # surface context + ask the start questions
│   ├── parse_transcript.py      # transcript → events + renderers
│   └── config.py · common.py · redact.py
├── tests/                       # pytest suite (summarizer, capture, security, …)
├── .github/                     # CI, CodeQL, secret scan, dependabot
├── recall.config.json        # config template / defaults
├── pyproject.toml               # ruff / pytest / bandit config (no runtime deps)
├── LICENSE · SECURITY.md · CONTRIBUTING.md
└── .gitignore
```
