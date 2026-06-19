#!/usr/bin/env python3
"""Build / overwrite .recall/context.md with the LOCAL summarizer.

Run on demand (the /recall:save command) — typically just before ending a
session. The Summary section is produced by the extractive summarizer; the rest
is derived deterministically from the transcript and git, so context.md is an
honest, reproducible digest of the session. No LLM, no network.
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import parse_transcript  # noqa: E402
import summarizer  # noqa: E402
from common import (  # noqa: E402
    context_path,
    ensure_output_dir,
    git_info,
    history_path,
    locate_transcript,
    project_name,
    read_text,
    write_text,
)
from config import load_config  # noqa: E402
from redact import redact  # noqa: E402


def _clean_for_summary(history_text):
    """Strip history.md's markdown chrome so the extractive summarizer sees prose,
    not headings / role labels / tool bullets."""
    out = []
    for line in history_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- ") or s.startswith("`"):  # tool-call bullet lines
            continue
        # Drop the **You:** / **Claude:** role prefixes, keep the spoken text.
        for prefix in ("**You:**", "**Claude:**"):
            if s.startswith(prefix):
                s = s[len(prefix):].strip()
        if s:
            out.append(s)
    return "\n".join(out)


def _bullets(items, limit, empty="(none)"):
    if not items:
        return empty
    shown = items[:limit]
    out = "\n".join(f"- {it}" for it in shown)
    if len(items) > limit:
        out += f"\n- …and {len(items) - limit} more"
    return out


def build(cwd, cfg, transcript_path):
    events = parse_transcript.parse(transcript_path)

    # Summarize the captured history if present (it's what the user expects to be
    # condensed); otherwise summarize the transcript prose directly.
    history_text = read_text(history_path(cwd, cfg))
    corpus = _clean_for_summary(history_text) if history_text else \
        parse_transcript.prose(events, cfg["max_input_chars"])
    corpus = corpus[-cfg["max_input_chars"]:]
    summary = summarizer.summarize(corpus, cfg["summary_sentences"])

    goal = parse_transcript.first_user_goal(events)
    last = parse_transcript.last_assistant_state(events)
    files = parse_transcript.touched_files(events)
    cmds = parse_transcript.commands(events)
    git = git_info(cwd) if cfg["include_git"] else ""

    ts = datetime.datetime.now().isoformat(timespec="seconds")
    summary_md = ("\n".join(f"- {s}" for s in summary) if summary
                  else "_(not enough captured to summarize)_")

    md = f"""# Project Context — {project_name(cwd)} (updated {ts})

_Generated locally by Recall — {summarizer.backend_name()}._

## 🎯 Goal
{(goal[:500] + "…") if len(goal) > 500 else (goal or "_(not detected — set it manually)_")}

## 🧭 Summary
{summary_md}

## 📂 Files touched
{_bullets(files, 30)}

## 🔧 Commands run
{_bullets(cmds, 15)}

## ⏱ Where we left off
{(last[:600] + "…") if len(last) > 600 else (last or "_(unknown)_")}
"""
    if git:
        md += f"\n## 🌿 Git ground-truth\n```\n{git}\n```\n"

    if cfg["redact"]:
        md = redact(md)
    return md


def run(cwd, transcript_path=None, quiet=False):
    cfg = load_config(cwd)
    transcript_path = transcript_path or locate_transcript(cwd)
    if not transcript_path or not os.path.exists(transcript_path):
        if not quiet:
            print("Recall: no session transcript found; nothing to summarize.")
        return 1

    md = build(cwd, cfg, transcript_path)
    ensure_output_dir(cwd, cfg)
    path = context_path(cwd, cfg)
    write_text(path, md)

    if not quiet:
        print(f"Recall: wrote {path}")
        print(f"Recall: summarizer = {summarizer.backend_name()}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Recall: build context.md locally")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--transcript")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        sys.exit(run(args.cwd, args.transcript, quiet=args.quiet))
    except Exception as exc:
        print(f"Recall error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
