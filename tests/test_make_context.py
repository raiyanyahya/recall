import os

import common
import make_context
from _util import assistant, make_jsonl, user
from config import load_config


def test_context_has_facts_and_clean_summary(tmp_path):
    cwd = str(tmp_path)
    t = os.path.join(cwd, "sessCCCC3333.jsonl")
    make_jsonl(t, [
        user("Refactor the database layer to Postgres and add tests"),
        assistant(
            "Migrated the connection layer to Postgres and added integration "
            "tests. Token sk-ant-ABCDEFGHIJKLMNOP123 should be redacted.",
            [("Write", {"file_path": "db.py"}), ("Bash", {"command": "pytest -q"})],
        ),
    ])

    assert make_context.run(cwd, transcript_path=t, quiet=True) == 0
    ctx = common.read_text(common.context_path(cwd, load_config(cwd)))

    # Deterministic facts.
    assert "Refactor the database layer to Postgres" in ctx  # goal
    assert "db.py" in ctx                                    # files touched
    assert "pytest -q" in ctx                                # commands run
    # Redaction applied to the written file.
    assert "sk-ant-ABCDEFGHIJKLMNOP123" not in ctx

    # The summary section must not contain history.md markdown chrome.
    summary = ctx.split("## 🧭 Summary")[1].split("## 📂")[0]
    assert "#" not in summary
    assert "`" not in summary
    assert "**You:**" not in summary and "**Claude:**" not in summary


def test_ignores_slash_command_meta_and_own_save(tmp_path):
    cwd = str(tmp_path)
    t = os.path.join(cwd, "sessDDDD4444.jsonl")
    make_jsonl(t, [
        user("Implement the parser module with full coverage"),
        assistant("Done.", [("Write", {"file_path": "parser.py"})]),
        # a /recall:save invocation: a command-meta user turn + the save command
        user("<command-name>/recall:save</command-name>"),
        assistant("Saving the context now.",
                  [("Bash", {"command": 'python3 "/x/scripts/make_context.py" --cwd .'})]),
    ])
    assert make_context.run(cwd, transcript_path=t, quiet=True) == 0
    ctx = common.read_text(common.context_path(cwd, load_config(cwd)))
    assert "Implement the parser module" in ctx     # real goal, not the slash command
    assert "command-name" not in ctx                # meta turn filtered out
    assert "make_context.py" not in ctx             # own save command not listed


def test_missing_transcript_returns_nonzero(tmp_path):
    cwd = str(tmp_path)
    assert make_context.run(cwd, transcript_path=os.path.join(cwd, "nope.jsonl"),
                            quiet=True) == 1
