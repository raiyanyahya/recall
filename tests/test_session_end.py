import json
import os

import common
from _util import assistant, make_jsonl, run_session_end, user
from config import load_config


def _transcript(cwd):
    t = os.path.join(cwd, "sessFFFF6666.jsonl")
    make_jsonl(t, [
        user("Build a small inventory service with several endpoints"),
        assistant("Scaffolded it.", [("Write", {"file_path": "inventory.py"})]),
    ])
    return t


def test_session_end_captures_but_does_not_autosave_by_default(tmp_path):
    cwd = str(tmp_path)
    t = _transcript(cwd)
    run_session_end(cwd, t, "sessFFFF6666")
    cfg = load_config(cwd)
    assert os.path.exists(common.history_path(cwd, cfg))      # history captured
    assert not os.path.exists(common.context_path(cwd, cfg))  # but no auto-save


def test_session_end_autosaves_context_when_enabled(tmp_path):
    cwd = str(tmp_path)
    with open(os.path.join(cwd, "recall.config.json"), "w", encoding="utf-8") as fh:
        json.dump({"auto_save_context": "on_end"}, fh)
    t = _transcript(cwd)
    run_session_end(cwd, t, "sessFFFF6666")
    cfg = load_config(cwd)
    ctx = common.context_path(cwd, cfg)
    assert os.path.exists(ctx)
    assert "inventory service" in common.read_text(ctx)
