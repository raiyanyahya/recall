# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Issue templates (bug report, feature request) and a pull request template.
- This changelog.

## [0.2.0] - 2026-06-19

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

## [0.1.0] - 2026-06-19

### Added
- Initial plugin: `SessionStart` / `SessionEnd` / `Stop` hooks, the
  `/recall:save`, `/recall:show`, and `/recall:load` commands, and a
  transcript summarizer with selectable backends (Ollama by default, Claude API
  optional), writing `.recall/context.md` and `.recall/history.md`.

[Unreleased]: https://github.com/raiyanyahya/recall/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/raiyanyahya/recall/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/raiyanyahya/recall/releases/tag/v0.1.0
