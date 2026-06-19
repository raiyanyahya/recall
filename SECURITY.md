# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's **Report a vulnerability**
(Security → Advisories) on this repository, or by email to the maintainer. Do not
open a public issue for a suspected vulnerability. You'll get an acknowledgement
within a few days.

## Security posture

Recall is designed to be safe by construction:

- **No network, no credentials.** The plugin makes no network calls and uses no
  API key. The summarizer is vendored, local Python (numpy is an optional
  accelerator). It reads your session transcript and writes only under
  `output_dir`.
- **Redaction.** A best-effort pass strips common secret shapes (API keys,
  tokens, `.env` assignments, PEM keys) before writing the committable md files.
  Best-effort, not a guarantee — review before committing.
- **Hardened git.** Ground-truth reads run `git` with `core.fsmonitor`,
  `diff.external`, hooks, and the pager disabled, so an untrusted cloned repo
  can't use its own git config to execute code. Set `include_git: false` to skip
  git entirely.
- **Confined writes.** `output_dir` is forced to stay inside the project; a
  repo-shipped config can't redirect writes outside it. Writes use `O_NOFOLLOW`
  so a planted symlink can't redirect them.
- **Scoped transcript.** Only the current project's transcript is read; there is
  no fallback to other projects' sessions.
- **Defensive hooks.** All hooks are stdlib-only and exit 0 on any error, so they
  cannot crash a session.

## Trust boundary for shared memory

`context.md` is injected into the model at session start. If you **commit
`.recall/` as shared team memory**, treat it like any other shared input: a
party with repo write access could craft a `context.md` to attempt prompt
injection. SessionStart fences the content and labels it untrusted data, and
Claude asks before relying on it — but if you don't fully trust who can write the
repo, keep `.recall/` git-ignored (the default).

## Not a Recall issue

If `claude` itself reports *"Invalid API key"*, that's the Claude Code CLI's own
authentication — usually a stale `ANTHROPIC_API_KEY` environment variable
shadowing your subscription login. `unset ANTHROPIC_API_KEY`. Recall has no
involvement in authentication.
