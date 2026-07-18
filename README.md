<h1 align="center">🔁</h1>
<h3 align="center">Recall — fully-local project memory for Claude Code</h3>

<p align="center">
  <a href="https://claude.com/claude-code"><img alt="Built for Claude Code" src="https://img.shields.io/badge/built%20for-Claude%20Code-CC785C"></a>
  <a href="#opencode"><img alt="OpenCode: opt-in support" src="https://img.shields.io/badge/opencode-opt--in-1a1a2e"></a>
  <a href="https://github.com/raiyanyahya/recall/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/raiyanyahya/recall/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/raiyanyahya/recall/actions/workflows/codeql.yml"><img alt="CodeQL" src="https://github.com/raiyanyahya/recall/actions/workflows/codeql.yml/badge.svg"></a>
  <a href="https://codecov.io/gh/raiyanyahya/recall"><img alt="Coverage" src="https://codecov.io/gh/raiyanyahya/recall/branch/master/graph/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
</p>


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
- **Saves your usage credits.** Two ways: (1) the summary is built locally, so
  capturing and updating your memory spends **zero** model tokens; and (2)
  resuming from a compact `context.md` (~1–2K tokens) instead of re-explaining the
  project from scratch each session means far fewer tokens spent per session —
  stretching your subscription's usage limits (or, on the API, lowering billed
  credits).
- **Nothing leaves your machine.** Your transcripts (code, paths, sometimes
  secrets) are never sent to any API. Most "memory" tools pipe your context to a
  model endpoint; Recall makes a privacy guarantee they can't. See
  [PRIVACY.md](PRIVACY.md) for the full policy.
- **Zero-friction.** No `pip install`, no local model to run, no key to configure,
  works offline. It starts working the moment the plugin loads.

Two files, written into your project under `.recall/`:

- **`history.md`** — *the log.* Append-only. Every session is captured here as it
  happens (your prompts, Claude's replies, the files touched and commands run).
- **`context.md`** — *the summary.* Overwritten by the local summarizer — the
  condensed "where are we right now" you load into the next session: goal,
  summary, **next steps / open threads**, files touched, and where you left off.

## "Doesn't Claude Code already have memory?"

It does — and Recall is complementary, not a replacement. The built-in options
solve different problems:

- **`CLAUDE.md` (and the `#` shortcut)** is *hand-written* memory: rules and notes
  **you** curate, loaded as **instructions Claude follows**. Great for "how I want
  you to work," but it's manual upkeep and it doesn't record what actually
  happened in a session.
- **`--continue` / `--resume`** replays a *prior conversation* — full fidelity, but
  it reloads the whole transcript (token-heavy) and is tied to your local session
  history on one machine, not a portable, readable digest.
- **Context compaction** condenses a conversation *within* a session; it isn't a
  durable record you reopen days later.

Recall fills the gap between these: an **automatic, deterministic record of what
each session did**, condensed into a compact resume point.

| | `CLAUDE.md` / `#` | `--continue` / `--resume` | **Recall** |
|---|---|---|---|
| What it is | Hand-written notes & rules | Reloads a prior conversation | Auto-captured session log + local summary |
| Upkeep | Manual | None (you pick the session) | None — written as you work |
| Holds | Instructions to follow | The full prior transcript | Goal, files, commands, where you left off, next steps |
| Cost to resume | Small | Large (replays full transcript) | ~1–2K tokens (compact digest) |
| Form | Markdown you edit | Local session state | Plaintext in `.recall/` — diffable & shareable |
| How Claude treats it | As instructions | As the conversation | Fenced as **untrusted reference data** |

In short: `CLAUDE.md` is *how I want you to work*; Recall is *here's what we did
last time and where we stopped* — produced offline, with no model tokens spent.

## How it works

| Moment | What happens |
|---|---|
| **During the session** | The `Stop` / `SessionEnd` hooks append new activity to `.recall/history.md`. Capture is incremental (only new turns) and fully local. |
| **At session start** | The `SessionStart` hook surfaces `context.md` and has Claude ask you two things: resume from the saved context? and keep logging this session? |
| **Before you wrap up** | You run `/recall:save`. The **local summarizer** reads `history.md` and (over)writes `context.md`. |
| **…or automatically** | Set `auto_save_context: "on_end"` and `context.md` regenerates every time a session ends — no `/recall:save` needed. |

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
| `auto_save_context` | `"off"` | Regenerate `context.md` when a session ends: `"off"` or `"on_end"`. |
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

## Other harnesses

Claude Code is Recall's first-class harness — the plugin install above is the
primary, fully supported path, and nothing in this section affects it. But the
memory Recall writes is plain markdown in `.recall/`, not harness state, so
other coding agents can produce and consume the very same files. Harness
support is always **opt-in**: nothing activates unless you explicitly set it
up. A nice consequence: memory is **shared across harnesses** — a Claude Code
user and an opencode user on the same repo write to the same `history.md`,
and either side's `context.md` resumes the other's work.

### OpenCode

**How plugin installs work in opencode.** Unlike Claude Code, [opencode](https://opencode.ai)
has no plugin marketplace and no in-CLI install command — there's no
`/plugin install` to run inside it. Plugins are loaded from files and config:
anything in a project's `.opencode/plugins/` (or the global
`~/.config/opencode/plugins/`) is auto-loaded at startup, custom commands are
markdown files in `.opencode/commands/`, and session-start context comes from
the `instructions` list in `opencode.json`. Recall plugs into exactly those
mechanisms — a small installer generates the files **once**, and opencode
picks them up automatically from then on.

**Set it up once per project** — not per session, not per machine boot:

```
git clone https://github.com/raiyanyahya/recall ~/recall
python3 ~/recall/scripts/install.py --opencode --project /path/to/your/project
```

Keep the clone around — the generated plugin points at it. The only reason to
ever re-run the installer is if you move the clone (or want to uninstall).

The installer writes exactly three things, all inside the target project:

| File | Purpose |
|---|---|
| `.opencode/plugins/recall.ts` | the capture shim, auto-loaded by opencode at startup |
| `.opencode/commands/recall-save.md` | the `/recall-save` command |
| `opencode.json` | adds `.recall/context.md` to `instructions` |

**From then on, every session is automatic:**

- **At session start**, opencode loads `.recall/context.md` (via
  `instructions`) — you resume where you left off, no re-explaining.
- **After every turn** (opencode's `session.idle` event), the shim appends new
  activity to `.recall/history.md`. It reads the session through
  `opencode export` — opencode's public CLI — never its internal storage.
- **Before wrapping up**, run `/recall-save` to regenerate `context.md` with
  the local summarizer — or set `auto_save_context: "on_end"` in
  `recall.config.json` and it regenerates after every turn on its own.

Same guarantees as the Claude Code path: fully local, no network, no API key;
capture honors `recall.config.json`, `.capture-paused`, and redaction; any
failure is a silent no-op so a session is never affected. Uninstall anytime
with `--opencode --uninstall` (your `.recall/` data stays), and the installer
never overwrites or deletes a file it didn't generate.

Two differences from the Claude Code path to be aware of:

- **Instructions, not fenced data.** opencode loads `context.md` through its
  `instructions` mechanism, without the untrusted-data fencing the Claude Code
  SessionStart hook applies. If you commit `.recall/` as shared team memory,
  only do so with collaborators you trust.
- **Tracks opencode's public CLI** (`session list`, `export`, the plugin
  events API), which is the stable surface — but opencode moves fast; if a
  release changes these, capture degrades to a silent no-op. File an issue.

### Codex and others

Not supported yet. The adapter seam (`scripts/harness_opencode.py`,
`--harness` on `make_context.py`) is where a new harness plugs in —
contributions welcome.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install pytest ruff bandit numpy   # numpy optional

ruff check scripts tests benchmarks    # lint
bandit -c pyproject.toml -r scripts    # security static analysis
pytest                                 # run the suite (also test without numpy)
python benchmarks/bench.py             # perf + quality numbers (human-readable)
python benchmarks/bench.py --check     # assert quality invariants (the CI gate)
claude plugin validate .               # official manifest validation
```

`benchmarks/bench.py` is a stdlib-only harness: alongside latency/throughput it
scores the summarizer's salient-sentence selection against lead/tail/random
baselines on a labeled fixture set and checks the numpy and pure-Python cores
select the **same** sentences. `--check` gates those quality invariants (it never
gates wall-clock timings). Redaction quality is covered by the unit suite
(`tests/test_redact.py`), so no secret-shaped fixtures live in the benchmark.

CI (`.github/workflows/`) runs lint + Bandit, the test suite across Python
3.9–3.13 **with and without numpy** (both summarizer paths), the benchmark
quality gate (both paths), CodeQL, secret scanning, and manifest JSON validation
on every push and PR. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Layout

```
recall/
├── .claude-plugin/plugin.json   # manifest
├── hooks/hooks.json             # SessionStart (ask/resume) · Stop+SessionEnd (capture)
├── commands/                    # /recall:save · show · log
├── scripts/
│   ├── summarizer.py            # vendored TF-IDF + TextRank (numpy optional)
│   ├── make_context.py          # build/overwrite context.md (--harness claude|opencode)
│   ├── capture.py               # append session activity to history.md
│   ├── session_start.py         # surface context + ask the start questions
│   ├── parse_transcript.py      # transcript → events + renderers
│   ├── harness_opencode.py      # opencode adapter (public CLI only) + opencode_capture.py
│   ├── install.py               # flag-based installer for opt-in harnesses (--opencode)
│   └── config.py · common.py · redact.py
├── integrations/opencode/       # generated-file templates (plugin shim, /recall-save)
├── tests/                       # pytest suite (summarizer, capture, security, …)
├── benchmarks/bench.py          # perf + quality harness (CI quality gate)
├── .github/                     # CI, CodeQL, secret scan, dependabot
├── recall.config.json        # config template / defaults
├── pyproject.toml               # ruff / pytest / bandit config (no runtime deps)
├── LICENSE · SECURITY.md · CONTRIBUTING.md
└── .gitignore
```

## Contributing & issues

Bugs and ideas are welcome — open an [issue](https://github.com/raiyanyahya/recall/issues/new/choose)
(bug-report and feature templates provided) or a pull request. See
[CONTRIBUTING.md](CONTRIBUTING.md) before submitting, and report security
vulnerabilities privately per [SECURITY.md](SECURITY.md) rather than in a public issue.

