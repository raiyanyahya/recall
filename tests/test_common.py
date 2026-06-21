import os
import shutil
import subprocess

import common
import pytest


def test_save_state_caps_tracked_sessions(tmp_path):
    cwd = str(tmp_path)
    cfg = {"output_dir": ".recall"}
    n = common._MAX_TRACKED_SESSIONS + 50
    common.save_state(cwd, cfg, {f"s{i}": i for i in range(n)})

    loaded = common.load_state(cwd, cfg)
    assert len(loaded) == common._MAX_TRACKED_SESSIONS
    assert f"s{n - 1}" in loaded            # newest kept
    assert "s0" not in loaded               # oldest pruned


def test_git_uncommitted_reports_rename_target(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    cwd = str(tmp_path)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

    def git(*args):
        subprocess.run(["git", "-C", cwd, *args], check=True, capture_output=True, env=env)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "old.txt").write_text("hi\n")
    git("add", "old.txt")
    git("commit", "-q", "-m", "init")
    git("mv", "old.txt", "new.txt")  # staged rename -> porcelain "R  old.txt -> new.txt"

    paths = common.git_uncommitted(cwd)
    assert "new.txt" in paths
    assert not any("->" in p for p in paths)
