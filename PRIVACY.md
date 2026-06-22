# Privacy Policy

_Last updated: 2026-06-22_

**Short version: Recall collects nothing, sends nothing, and runs entirely on
your machine.** There is no server, no account, no telemetry, and no network
connection of any kind.

## What Recall does

Recall is a fully-local memory plugin for Claude Code. It reads your local
session transcript and writes its output into the `.recall/` directory inside
your project. The two files it produces for you are:

- `.recall/history.md` — an append-only log of each session (your prompts,
  Claude's replies, files touched, and commands run).
- `.recall/context.md` — a condensed summary of where you left off, produced by
  a classical Python summarizer that runs locally.

It also keeps small internal bookkeeping files in the same directory (for
example, capture progress and a pause marker). Recall never writes outside this
directory, and it refuses paths that would escape your project.

## What data is handled

Recall processes the contents of your Claude Code session — prompts, replies,
file paths, and commands — solely to write the two files above. This data:

- **Stays on your machine.** It is written only to the `.recall/` directory in
  your project (the location is configurable via `output_dir`).
- **Is owned and controlled by you.** You can read, edit, or delete these files
  at any time. Deleting `.recall/` removes everything Recall has stored.

## What Recall does NOT do

- **No network access.** Recall makes no HTTP requests and uses no networking
  libraries. It works fully offline.
- **No telemetry or analytics.** Nothing about your usage is collected or
  reported.
- **No third-party services.** Your data is never sent to any API, model
  endpoint, or external party — including any AI model. The only AI in the loop
  is Claude Code itself; Recall's summarization is a local algorithm.
- **No accounts or keys.** Recall requires no sign-up, API key, or credentials.

The only external program Recall invokes is your local `git`, read-only, to
record branch and diff information. It is configured so it cannot prompt for
credentials or contact a remote (`GIT_TERMINAL_PROMPT=0`), and you can disable
it entirely by setting `include_git` to `false`.

## Secret redaction

Because session transcripts can contain secrets, Recall applies best-effort
redaction (enabled by default via the `redact` setting) before writing its
files. It removes common patterns such as API keys, AWS access keys,
GitHub/Slack tokens, JWTs, private keys, and `SECRET`/`TOKEN`/`PASSWORD`/
`API_KEY` environment-variable values.

This is a safety net, **not a guarantee**. Treat the `.recall/` files as you
would your source code. They are git-ignored by default; keep them ignored
unless you intend to commit them as shared team memory, and review them before
sharing.

## Changes to this policy

Any changes will be reflected in this file in the repository, with the "Last
updated" date above.

## Contact

Questions or concerns? Open an issue at
https://github.com/raiyanyahya/recall/issues
