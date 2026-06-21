import os
import shutil
import subprocess

import common
import pytest


def test_output_dir_confined_to_project(tmp_path):
    cwd = str(tmp_path)
    base = os.path.realpath(cwd)
    assert common.output_dir(cwd, {"output_dir": ".recall"}) == os.path.join(base, ".recall")
    # Absolute paths and traversal must be rejected -> fall back to default.
    assert common.output_dir(cwd, {"output_dir": "/etc/evil"}) == os.path.join(base, ".recall")
    assert common.output_dir(cwd, {"output_dir": "../../etc"}) == os.path.join(base, ".recall")
    # A nested in-project dir is allowed.
    assert common.output_dir(cwd, {"output_dir": "memory/x"}).startswith(base + os.sep)


def test_output_dir_rejects_symlinked_default(tmp_path):
    # A malicious clone can ship `.recall` itself as a symlink pointing outside
    # the project. The default fallback must not follow it outside cwd; with no
    # safe location, output_dir refuses (returns None) and dependent paths too.
    proj = tmp_path / "proj"
    proj.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, proj / ".recall")
    cwd = str(proj)

    assert common.output_dir(cwd, {"output_dir": ".recall"}) is None
    assert common.history_path(cwd, {"output_dir": ".recall"}) is None
    assert common.ensure_output_dir(cwd, {"output_dir": ".recall"}) is None


def test_capture_does_not_write_outside_via_symlinked_recall(tmp_path):
    import capture

    proj = tmp_path / "proj"
    proj.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, proj / ".recall")

    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        '{"type":"user","message":{"content":"do a thing"}}\n', encoding="utf-8"
    )
    capture.capture_session({"cwd": str(proj),
                             "transcript_path": str(transcript),
                             "session_id": "abc123"})

    # Nothing must have been written into the symlink target.
    assert list(outside.iterdir()) == []


def test_locate_transcript_no_cross_project_fallback():
    assert common.locate_transcript("/nonexistent/project/zzz999") is None


def test_write_text_refuses_to_follow_symlink(tmp_path):
    victim = tmp_path / "VICTIM.txt"
    victim.write_text("original")
    link = tmp_path / "context.md"
    os.symlink(victim, link)
    with pytest.raises(OSError):
        common.write_text(str(link), "OVERWRITTEN")
    assert victim.read_text() == "original"


def test_git_hardening_blocks_malicious_diff_external(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    cwd = str(tmp_path)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

    def git(*args):
        subprocess.run(["git", "-C", cwd, *args], check=True,
                       capture_output=True, env=env)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("hi\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", "init")
    (tmp_path / "a.txt").write_text("changed\n")

    marker = tmp_path / "PWNED"
    git("config", "diff.external", "sh -c 'touch %s' #" % marker)

    info = common.git_info(cwd)  # runs git diff/log internally
    assert not marker.exists(), "malicious diff.external was executed"
    assert "git diff --stat" in info  # still produced real output
