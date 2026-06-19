# Contributing to Recall

Thanks for helping! Recall is intentionally small, dependency-free, and local.
Please keep it that way.

## Principles

- **No runtime dependencies, no network.** The default path must work on a stock
  Python 3 with no `pip install`. `numpy` may only be used as an optional
  accelerator behind a `try/except ImportError` fallback.
- **Hooks must never crash a session.** Every hook entry point is stdlib-only and
  wrapped so it exits 0 on any error.
- **Local-only.** No API keys, no external model calls, no telemetry.

## Dev setup

No install needed to run the plugin. For the dev tools:

```bash
python -m venv .venv && . .venv/bin/activate
pip install pytest ruff bandit numpy   # numpy optional, to test the fast path
```

## Before you push

```bash
ruff check scripts tests          # style + lint
bandit -c pyproject.toml -r scripts   # security static analysis
pytest                             # test suite (run with and without numpy)
claude plugin validate .           # official manifest validation
```

Run the suite **with and without numpy installed** — both summarizer paths must
pass. CI does this automatically across Python 3.9–3.13.

## Manual end-to-end test

```bash
claude --plugin-dir .              # load the plugin in a real session
# do some work, then:
/recall:save
# open a fresh session and confirm it resumes from .recall/context.md
```

## Conventions

- Keep lines ≤ 100 chars; keep functions small and defensive.
- All transcript-shape knowledge lives in `scripts/parse_transcript.py`.
- Add a test under `tests/` for any behavior change.
