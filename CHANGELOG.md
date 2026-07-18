# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-07-18

### Added
- **Opt-in OpenCode support** (#10). `python3 scripts/install.py --opencode`
  wires Recall into an [opencode](https://opencode.ai) project: a generated
  plugin shim captures every `session.idle` into the same `.recall/history.md`,
  a `/recall-save` command regenerates `context.md` locally
  (`make_context.py --harness opencode`), and `opencode.json` gains
  `.recall/context.md` under `instructions` for session-start resume. Fully
  reversible (`--uninstall`), and the installer never overwrites or deletes a
  file it didn't generate. The adapter (`scripts/harness_opencode.py`) talks
  only to opencode's public CLI (`session list`, `export`) — never its internal
  storage — and filters sessions by project directory, preserving the
  scoped-transcript guarantee. **The Claude Code path is untouched**: same
  hooks, commands, and manifest; `make_context.py` defaults to
  `--harness claude` with identical behavior, and nothing activates unless the
  installer is explicitly run.
- CI: an installer smoke test in the `validate` job guards the shipped
  templates end-to-end — placeholder substitution, the generated shim parsing
  as valid ESM, a parseable generated `opencode.json`, and a clean uninstall.

### Changed
- README: harness documentation restructured under an "Other harnesses"
  section (how opencode plugin loading works, one-time setup, per-session
  behavior), with an opencode badge.

## [0.3.6] - 2026-06-25

### Fixed
- **Windows: the plugin no longer fails silently.** On a standard Windows install
  (no `python3` on PATH, default cp1252 console) the hooks ran but captured and
  surfaced nothing — every failure swallowed by the defensive `except` that keeps
  Recall from ever crashing a session. Three independent OS-specific bugs, now
  fixed (reported in #6):
  - **`python3` not found.** `hooks.json` (all three hooks) and the `/recall:save`
    command invoked `python3`, which the standard Windows installer doesn't
    provide, so capture and the recap never ran. They now fall back to `python`
    (`python3 … || python …`, valid in both `cmd` and POSIX `sh`).
  - **Transcript directory never matched.** `locate_transcript()` didn't reproduce
    Claude Code's Windows project-dir encoding (the drive colon, backslashes and
    spaces all become `-`, e.g. `C:\foo bar` → `C--foo-bar`), so `/recall:save`
    and the resume fallback reported "no session transcript found". The candidate
    is now derived by replacing every non-alphanumeric character — which also
    fixes Unix/macOS paths that contain spaces.
  - **Recap crashed on emoji.** `session_start.py` prints a 📒 and the saved
    context; under the default cp1252 console `print()` raised
    `UnicodeEncodeError`, swallowed by the hook's bare `except`, so the recap
    never surfaced even when `context.md` existed. stdout is now reconfigured to
    UTF-8.
- **Marketplace version resynced.** `.claude-plugin/marketplace.json` had been
  left at 0.3.4 (missed in the 0.3.5 release); it now tracks `plugin.json` again.

## [0.3.5] - 2026-06-23

### Added
- **Privacy policy** (`PRIVACY.md`), linked from the README. Documents that
  Recall runs fully locally — no network access, telemetry, accounts, or
  third-party/model calls, and all output stays under `.recall/` — and that the
  built-in secret redaction is a best-effort safety net, not a guarantee.

## [0.3.4] - 2026-06-22

### Added
- **Benchmark + quality harness** (`benchmarks/bench.py`, stdlib-only). Reports
  summarizer latency, the numpy vs pure-Python speedup, transcript-parse
  throughput, and compression; and scores the summarizer's salient-sentence
  selection against lead/tail/random baselines on a labeled fixture set. A
  `--check` mode gates the quality invariants (summarizer beats the baselines and
  both backends select identical sentences) and runs in CI on both the numpy and
  pure-Python paths.

### Fixed
- **Deterministic summaries across backends.** Summary sentence ranking now
  rounds away the sub-epsilon score differences between the numpy and pure-Python
  cores and breaks ties by position, so both always select the same sentences — a
  committed `context.md` no longer depends on whether numpy is installed. (Caught
  by the new harness.)
- **Cleaner "Next steps / open threads".** The heuristic no longer surfaces
  echoed prompt/instruction text (e.g. "in 3-4 sentences, list the next steps"),
  trivial questions ("looks good, anything left?"), markdown header/label lines,
  or Recall's own injected boilerplate. The over-broad bare `next` cue was
  dropped (genuine steps still match `still need` / `should` / `todo` / …), and a
  bare question must now be substantive to count. (Surfaced by a live end-to-end
  test of the plugin in real Claude Code.)

## [0.3.3] - 2026-06-22

### Fixed
- **Malformed transcript lines no longer break capture.** A single non-object
  JSONL line (or a turn whose `message`/tool `input` wasn't an object) raised an
  `AttributeError` in the parser; in the capture hook that error was swallowed
  *and the byte offset never advanced*, so history logging silently died for the
  rest of the session (and `/recall:save` exited non-zero). Such lines are now
  skipped gracefully.
- **Corrupt `.capture.json` offset** no longer crashes capture — a non-integer
  entry falls back to re-capturing the session from the top.
- `git_uncommitted` now reports the destination path for renames instead of the
  raw `old -> new` porcelain string.

### Changed
- **Config values are type-validated.** A project-shipped `recall.config.json` is
  untrusted, so a wrong-typed value (e.g. `output_dir` as a number,
  `summary_sentences` as a string, a non-positive char cap) now falls back to the
  default instead of risking a `TypeError`. A bad `redact` value fails safe to
  `true`.
- **`.capture.json` is bounded.** Per-session offsets are capped (most-recent 500
  sessions retained) so the state file can't grow without bound; the active
  session is always preserved.

## [0.3.2] - 2026-06-21

### Security
- Closed a path-confinement bypass in `output_dir`: a pre-planted symlink at the
  default `.recall` (e.g. shipped in an untrusted clone) could redirect Recall's
  writes outside the project, because the fallback re-resolved the same symlink.
  The fallback is now validated too; when no in-project location is safe Recall
  refuses to write (`output_dir` returns None) rather than landing outside the
  tree. Added regression tests covering the symlinked-`.recall` case end to end.

## [0.3.1] - 2026-06-20

### Added
- **Code coverage**: tests now run under `pytest-cov` (branch coverage, config in
  `pyproject.toml`), CI uploads the report to Codecov from a single matrix cell,
  and the README carries a coverage badge.

### Changed
- Pointed the CI/CodeQL workflow triggers and the README badges at the `master`
  default branch (were `main`), so pushes to the default branch run and report.

## [0.3.0] - 2026-06-20

### Added
- **Opt-in auto-save**: `auto_save_context: "on_end"` regenerates `context.md`
  automatically when a session ends (via the SessionEnd hook), so memory stays
  current without running `/recall:save`. Default `"off"`.
- **"Next steps / open threads" section** in `context.md` — a local heuristic
  surfaces unfinished work (next-step cues, open questions, uncommitted files).
- Issue templates (bug report, feature request) and a pull request template.
- This changelog.

### Changed
- `/recall:save` now derives its deterministic facts (goal, files, commands) from
  the most recent *substantive* session, so saving from a fresh/empty session
  falls back to your last real work instead of producing an empty summary.
- Slash-command invocations (e.g. running `/recall:save`) are filtered out of the
  transcript so they never appear as the Goal or as recorded activity.
- Bumped GitHub Actions: `actions/checkout` v4→v7, `actions/setup-python`
  v5→v6, `gitleaks/gitleaks-action` v2→v3, `github/codeql-action` v3→v4.

### Fixed
- Granted the secret-scan job `pull-requests: read` so gitleaks can list PR
  commits on `pull_request` events (was failing with HTTP 403).

## 0.2.0 - 2026-06-19

Complete rewrite to a **fully-local** design for people running Claude Code on a
subscription: the only AI in the loop is Claude Code itself, and summarization is
done by a vendored classical summarizer.

### Changed
- `context.md` is now produced by a vendored **TF-IDF + TextRank** extractive
  summarizer (numpy used as an optional accelerator, pure-Python fallback
  otherwise). No `pip install` required.
- `history.md` capture is incremental by **byte offset** (only new turns are read
  each turn) and defers partial trailing lines until complete.

### Removed
- The Ollama and Claude API summarizer backends, and with them any need for an
  `ANTHROPIC_API_KEY`, network access, or a separate local model.

### Security
- Hardened `git` ground-truth reads against untrusted-repo code execution
  (`core.fsmonitor`, `diff.external`, hooks, pager all disabled; `--no-ext-diff`).
- Confined `output_dir` to within the project (no absolute / `..` escapes).
- Symlink-safe writes via `O_NOFOLLOW`.
- Scoped transcript discovery to the current project only (no cross-project read).
- Best-effort secret redaction before writing the committable md files.
- SessionStart fences injected `context.md` as untrusted data.

### Added
- Pytest suite under `tests/`; CI (ruff, Bandit, pytest across Python 3.9–3.13
  with and without numpy), CodeQL, gitleaks secret scanning, Dependabot.
- `.claude-plugin/marketplace.json` (the repo is its own installable marketplace).
- `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, `pyproject.toml`.

## 0.1.0 - 2026-06-19

### Added
- Initial plugin: `SessionStart` / `SessionEnd` / `Stop` hooks, the
  `/recall:save`, `/recall:show`, and `/recall:load` commands, and a
  transcript summarizer with selectable backends (Ollama by default, Claude API
  optional), writing `.recall/context.md` and `.recall/history.md`.

[Unreleased]: https://github.com/raiyanyahya/recall/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/raiyanyahya/recall/releases/tag/v0.4.0
[0.3.6]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.6
[0.3.5]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.5
[0.3.4]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.4
[0.3.3]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.3
[0.3.2]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.2
[0.3.1]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.1
[0.3.0]: https://github.com/raiyanyahya/recall/releases/tag/v0.3.0
