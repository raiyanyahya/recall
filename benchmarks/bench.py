#!/usr/bin/env python3
"""Recall benchmark + quality harness — stdlib only (numpy optional, like the plugin).

Two kinds of measurement:

* **Performance** (informational): summarizer latency, the numpy vs pure-Python
  speedup, transcript-parse throughput, and compression ratio.
* **Quality** (gated): how well the extractive summarizer actually selects the
  salient content, scored against lead / tail / random baselines on a labeled
  fixture set, and that the two summarizer backends pick the *same* sentences.

(Redaction quality is exercised separately by the unit suite — see
tests/test_redact.py — so no secret-shaped fixtures need to live here.)

Usage:
    python benchmarks/bench.py          # full human-readable report
    python benchmarks/bench.py --check  # assert quality invariants; nonzero on regress (CI)

`--check` only asserts machine-independent quality facts — never wall-clock
timings, which are reported but never gated.
"""

import argparse
import json
import os
import random
import statistics
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts"))

import parse_transcript  # noqa: E402
import summarizer  # noqa: E402


def _norm(s):
    # Match on content only: collapse whitespace, drop trailing sentence
    # punctuation (the splitter keeps it), and fold case.
    return " ".join(s.split()).rstrip(".!?").strip().lower()


def _median_ms(fn, runs=7):
    fn()  # warm up
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    return statistics.median(times)


def _have_numpy():
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


# --------------------------------------------------------------------------- #
# Quality fixtures: each "session" has a coherent main thread (signal) plus
# scattered, one-off digressions (noise). A good extractive summary should keep
# the recurring thread and drop the digressions — so "did a kept sentence come
# from `signal`?" is a real, reference-free quality signal. Sentences are clause
# length (>= the summarizer's min) and free of mid-sentence ". " so they survive
# sentence splitting cleanly.
# --------------------------------------------------------------------------- #
SESSIONS = [
    {
        "name": "auth-refactor",
        "signal": [
            "We refactored the authentication module to issue short-lived access tokens",
            "The authentication service now signs tokens with a rotating key",
            "Token refresh was added so the authentication flow no longer logs users out",
            "We covered the authentication module with tests for expiry and refresh",
            "The login endpoint now rejects tokens whose authentication signature is stale",
            "Authentication errors are surfaced with a clear message to the client",
        ],
        "noise": [
            "By the way the office coffee machine was broken again this morning",
            "Someone asked about the lunch order for the team offsite next week",
            "The weather forecast predicts heavy rain across the region tomorrow",
            "A reminder went out about updating personal emergency contact details",
            "We briefly chatted about a movie that came out over the weekend",
            "The parking garage will be closed for maintenance on Friday afternoon",
        ],
    },
    {
        "name": "db-postgres-migration",
        "signal": [
            "We migrated the database layer from sqlite to postgres for concurrency",
            "The postgres connection pool was tuned to handle the migration load",
            "Database queries were rewritten to use postgres parameterized statements",
            "We added a migration script that moves existing rows into postgres",
            "Integration tests now run against a real postgres database in a container",
            "The database rollback path restores the previous postgres snapshot safely",
        ],
        "noise": [
            "The hallway printer is once again out of toner and needs a refill",
            "There is an all-hands meeting scheduled for the end of the month",
            "A colleague shared photos from their recent hiking trip up north",
            "The vending machine now accepts contactless card payments downstairs",
            "We discussed whether to reschedule the book club to a later evening",
            "The new badge readers at the front entrance were installed yesterday",
        ],
    },
    {
        "name": "summarizer-perf",
        "signal": [
            "We optimized the summarizer by vectorizing the textrank power iteration",
            "The summarizer keeps a pure python fallback when numpy is unavailable",
            "Sentence ranking in the summarizer is capped to bound worst case cost",
            "We profiled the summarizer and removed a redundant similarity pass",
            "The summarizer now reuses the idf table across the ranking iterations",
            "Summarizer output stays in original order after the textrank scoring",
        ],
        "noise": [
            "The team debated the merits of standing desks versus regular desks",
            "A new espresso blend was added to the kitchen on the third floor",
            "Someone lost a blue umbrella in the main conference room last week",
            "The fire drill scheduled for this quarter was pushed to next month",
            "We talked about the soccer match results from the weekend tournament",
            "The plants near the window need watering twice a week according to the note",
        ],
    },
]


def _pool_and_signal(session):
    """Candidate sentence pool (post-split) and the set of normalized signal
    sentences that survived splitting — the shared basis for every method.

    Whole sentences are shuffled (deterministically) so a lead/tail baseline gets
    no free signal from authoring order; content is the only thing that differs.
    """
    items = [s if s.endswith(".") else s + "." for s in
             session["signal"] + session["noise"]]
    random.Random(sum(map(ord, session["name"]))).shuffle(items)
    corpus = " ".join(items)
    pool = summarizer.split_sentences(corpus)
    signal = {_norm(s) for s in session["signal"]}
    signal_in_pool = [s for s in pool if _norm(s) in signal]
    return corpus, pool, signal, signal_in_pool


def _prf(selected, signal, n_signal, k):
    sel = [s for s in selected if s]
    tp = sum(1 for s in sel if _norm(s) in signal)
    precision = tp / len(sel) if sel else 0.0
    recall = tp / min(k, n_signal) if n_signal else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def selection_quality(k=5):
    """Macro-averaged precision/recall/F1 of salient-sentence selection for the
    real summarizer vs lead-k / tail-k / random-k baselines."""
    methods = ("textrank", "lead", "tail", "random")
    acc = {m: [0.0, 0.0, 0.0] for m in methods}
    for session in SESSIONS:
        corpus, pool, signal, signal_in_pool = _pool_and_signal(session)
        n_sig = len(signal_in_pool)
        rng = random.Random(1234)
        picks = {
            "textrank": summarizer.summarize(corpus, k),
            "lead": pool[:k],
            "tail": pool[-k:],
            "random": rng.sample(pool, min(k, len(pool))),
        }
        for m in methods:
            p, r, f = _prf(picks[m], signal, n_sig, k)
            acc[m][0] += p
            acc[m][1] += r
            acc[m][2] += f
    n = len(SESSIONS)
    return {m: tuple(v / n for v in acc[m]) for m in methods}


def backend_equivalence(k=5):
    """Do the numpy and pure-Python TextRank cores select the same sentences?
    Returns (checked, mismatches). checked=False when numpy isn't installed."""
    if not _have_numpy():
        return False, []
    mismatches = []
    for session in SESSIONS:
        corpus, pool, _, _ = _pool_and_signal(session)
        sents = summarizer.split_sentences(corpus)
        if len(sents) > summarizer._MAX_RANK:
            sents = sents[-summarizer._MAX_RANK:]
        toks = [summarizer._tokenize(s) for s in sents]
        idf = summarizer._idf(toks)
        np_sel = summarizer._select(sents, summarizer._textrank_numpy(toks, idf), k)
        py_sel = summarizer._select(sents, summarizer._textrank_python(toks, idf), k)
        if np_sel != py_sel:
            mismatches.append(session["name"])
    return True, mismatches


# --------------------------------------------------------------------------- #
# Performance (informational only)
# --------------------------------------------------------------------------- #
def _make_corpus(n):
    topics = [s for sess in SESSIONS for s in sess["signal"] + sess["noise"]]
    rng = random.Random(42)
    return " ".join(f"In step {i} {rng.choice(topics)} and we verified the result."
                    for i in range(n))


def report_performance():
    print("== Performance (informational; never gated) ==")
    print(f"summarizer backend: {summarizer.backend_name()}\n")
    have_np = _have_numpy()
    print(f"{'sentences':>9} | {'summarize':>10} | {'numpy core':>11} | "
          f"{'pure-py core':>12} | speedup")
    for n in (50, 100, 200, 400, 800):
        corpus = _make_corpus(n)
        sents = summarizer.split_sentences(corpus)
        capped = sents[-summarizer._MAX_RANK:] if len(sents) > summarizer._MAX_RANK else sents
        toks = [summarizer._tokenize(s) for s in capped]
        idf = summarizer._idf(toks)
        full = _median_ms(lambda c=corpus: summarizer.summarize(c, 8))
        tpy = _median_ms(lambda t=toks, d=idf: summarizer._textrank_python(t, d))
        if have_np:
            tnp = _median_ms(lambda t=toks, d=idf: summarizer._textrank_numpy(t, d))
            print(f"{n:>9} | {full:>8.2f}ms | {tnp:>9.2f}ms | {tpy:>10.2f}ms | {tpy / tnp:>4.0f}x")
        else:
            print(f"{n:>9} | {full:>8.2f}ms | {'n/a':>11} | {tpy:>10.2f}ms |    -")

    print("\ncompression (input -> kept summary, k=8):")
    for n in (100, 400):
        corpus = _make_corpus(n)
        out = summarizer.summarize(corpus, 8)
        ci, co = len(corpus), sum(len(s) for s in out)
        print(f"  {n:>3} sentences: {ci:>7} -> {co:>5} chars  ({co / ci * 100:4.1f}% kept, "
              f"~{ci // 4}->{co // 4} tokens)")

    lines = []
    for i in range(1000):
        lines.append(json.dumps({"type": "user", "message": {"content": f"prompt {i}"}}))
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": f"reply {i}"},
            {"type": "tool_use", "name": "Edit", "input": {"file_path": f"src/m{i}.py"}}]}}))
    t = _median_ms(lambda: parse_transcript.parse_lines(lines))
    print(f"\ntranscript parse: {len(lines)} lines in {t:.2f}ms "
          f"({len(lines) / (t / 1000):,.0f} lines/sec)")


def report_quality():
    print("\n== Quality (gated by --check) ==")
    q = selection_quality()
    print("salient-sentence selection (macro avg over fixtures, k=5):")
    print(f"  {'method':>8} | {'precision':>9} | {'recall':>7} | {'F1':>5}")
    for m in ("textrank", "lead", "tail", "random"):
        p, r, f = q[m]
        star = "  <- Recall" if m == "textrank" else ""
        print(f"  {m:>8} | {p:>9.2f} | {r:>7.2f} | {f:>5.2f}{star}")

    checked, mism = backend_equivalence()
    if checked:
        print(f"\nbackend equivalence (numpy vs pure-Python top-k): "
              f"{'IDENTICAL' if not mism else 'MISMATCH on ' + ', '.join(mism)}")
    else:
        print("\nbackend equivalence: skipped (numpy not installed)")


def check():
    """Assert machine-independent quality invariants. Returns a list of failures."""
    failures = []
    q = selection_quality()
    tr_f1 = q["textrank"][2]
    rand_f1 = q["random"][2]
    lead_f1 = q["lead"][2]
    if not tr_f1 >= 0.60:
        failures.append(f"summarizer F1 {tr_f1:.2f} below floor 0.60")
    if not tr_f1 > rand_f1:
        failures.append(f"summarizer F1 {tr_f1:.2f} not better than random {rand_f1:.2f}")
    if not tr_f1 >= lead_f1:
        failures.append(f"summarizer F1 {tr_f1:.2f} worse than lead baseline {lead_f1:.2f}")

    checked, mism = backend_equivalence()
    if checked and mism:
        failures.append("numpy and pure-Python backends disagree on: " + ", ".join(mism))

    return failures


def main():
    ap = argparse.ArgumentParser(description="Recall benchmark + quality harness")
    ap.add_argument("--check", action="store_true",
                    help="assert quality invariants (CI gate); print PASS/FAIL and exit")
    args = ap.parse_args()

    if args.check:
        failures = check()
        if failures:
            print("bench --check: FAIL")
            for f in failures:
                print(f"  - {f}")
            sys.exit(1)
        print("bench --check: PASS (summarizer beats baselines, backends agree)")
        sys.exit(0)

    report_performance()
    report_quality()


if __name__ == "__main__":
    main()
