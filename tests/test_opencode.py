"""OpenCode integration: adapter parsing, incremental capture, --harness save,
and the flag-based installer. The opencode CLI is never invoked — every test
monkeypatches the adapter's subprocess seam (_run_opencode) or higher."""

import json

import harness_opencode
import install
import make_context
import opencode_capture
import parse_transcript

GOAL = "add jwt auth to the api"


def export_doc():
    return {
        "info": {"directory": "/proj", "title": "auth work"},
        "messages": [
            {"info": {"role": "user"},
             "parts": [{"type": "text", "text": GOAL}]},
            {"info": {"role": "assistant"},
             "parts": [
                 {"type": "step-start"},
                 {"type": "reasoning", "text": "thinking hard"},
                 {"type": "text", "text": "I'll add the middleware."},
                 {"type": "tool", "tool": "edit",
                  "state": {"status": "completed",
                            "input": {"filePath": "/proj/api.py"}}},
                 {"type": "tool", "tool": "bash",
                  "state": {"status": "completed",
                            "input": {"command": "pytest -q"}}},
                 {"type": "step-finish"},
             ]},
        ],
    }


# ---------------------------------------------------------------- adapter

def test_events_map_roles_tools_and_files():
    events = harness_opencode.events_from_export(export_doc())
    assert [e["role"] for e in events] == ["user", "assistant", "tool", "tool"]
    assert events[0]["text"] == GOAL
    # tool names are normalized to the Claude-style spelling
    assert events[2]["tool"] == "Edit" and events[2]["files"] == ["/proj/api.py"]
    assert events[3]["tool"] == "Bash" and events[3]["detail"] == "pytest -q"


def test_events_skip_reasoning_steps_and_synthetic_text():
    doc = export_doc()
    doc["messages"][0]["parts"].append(
        {"type": "text", "text": "injected by a command", "synthetic": True})
    events = harness_opencode.events_from_export(doc)
    joined = " ".join(e["text"] for e in events)
    assert "thinking hard" not in joined
    assert "injected by a command" not in joined


def test_events_tolerate_garbage():
    assert harness_opencode.events_from_export(None) == []
    assert harness_opencode.events_from_export({}) == []
    assert harness_opencode.events_from_export({"messages": "nope"}) == []
    doc = {"messages": [42, {"info": {"role": "system"}, "parts": []},
                        {"info": {"role": "assistant"},
                         "parts": [7, {"type": "tool", "tool": None,
                                       "state": "broken"}]}]}
    events = harness_opencode.events_from_export(doc)
    assert all(e["role"] == "tool" for e in events)  # nothing crashes


def test_recall_internal_commands_are_not_recorded():
    doc = export_doc()
    doc["messages"][1]["parts"].append(
        {"type": "tool", "tool": "bash",
         "state": {"input": {"command": "python3 x/make_context.py --harness opencode"}}})
    events = harness_opencode.events_from_export(doc)
    assert all("make_context.py" not in e["detail"] for e in events)


def test_downstream_helpers_work_on_adapter_events():
    events = harness_opencode.events_from_export(export_doc())
    assert parse_transcript.first_user_goal(events) == GOAL
    assert parse_transcript.commands(events) == ["pytest -q"]
    assert parse_transcript.touched_files(events) == ["/proj/api.py"]
    assert GOAL in parse_transcript.render_history(events)


def test_json_tolerates_stray_log_lines():
    assert harness_opencode._json('INFO starting\n{"a": 1}') == {"a": 1}
    assert harness_opencode._json("log\n[1, 2]") == [1, 2]
    assert harness_opencode._json("no json here") is None
    assert harness_opencode._json("") is None


def test_project_sessions_filters_by_directory_and_sorts(tmp_path, monkeypatch):
    rows = [
        {"id": "old", "directory": str(tmp_path), "updated": 10},
        {"id": "other", "directory": str(tmp_path / "elsewhere"), "updated": 99},
        {"id": "new", "directory": str(tmp_path), "updated": 20},
        {"directory": str(tmp_path), "updated": 30},  # no id -> ignored
    ]
    monkeypatch.setattr(harness_opencode, "_run_opencode",
                        lambda args, timeout: json.dumps(rows))
    assert harness_opencode.project_sessions(str(tmp_path)) == ["new", "old"]


def test_collect_events_prefers_a_session_with_a_goal(monkeypatch):
    toolonly = [{"role": "tool", "text": "", "tool": "Bash",
                 "detail": "ls", "files": []}]
    withgoal = harness_opencode.events_from_export(export_doc())
    monkeypatch.setattr(harness_opencode, "project_sessions",
                        lambda cwd: ["s1", "s2"])
    monkeypatch.setattr(harness_opencode, "export_events",
                        lambda sid: {"s1": toolonly, "s2": withgoal}[sid])
    sid, events = harness_opencode.collect_events("/proj")
    assert sid == "s2" and parse_transcript.first_user_goal(events) == GOAL


# ---------------------------------------------------------------- capture

def test_capture_appends_incrementally(tmp_path, monkeypatch):
    cwd = str(tmp_path)
    first = harness_opencode.events_from_export(export_doc())
    feed = {"events": first}
    monkeypatch.setattr(harness_opencode, "export_events",
                        lambda sid: feed["events"])

    opencode_capture.capture_session(cwd, "ses_abc123")
    hist = (tmp_path / ".recall" / "history.md").read_text(encoding="utf-8")
    assert "(opencode)" in hist and hist.count(GOAL) == 1

    # same export again: nothing new -> nothing appended
    opencode_capture.capture_session(cwd, "ses_abc123")
    hist2 = (tmp_path / ".recall" / "history.md").read_text(encoding="utf-8")
    assert hist2 == hist

    # session grows -> only the new tail lands
    feed["events"] = first + [{"role": "user", "text": "now add tests",
                               "tool": "", "detail": "", "files": []}]
    opencode_capture.capture_session(cwd, "ses_abc123")
    hist3 = (tmp_path / ".recall" / "history.md").read_text(encoding="utf-8")
    assert hist3.count(GOAL) == 1 and "now add tests" in hist3

    state = json.loads((tmp_path / ".recall" / ".capture.json").read_text())
    assert state["oc:ses_abc123"] == len(feed["events"])


def test_capture_honors_pause_marker(tmp_path, monkeypatch):
    cwd = str(tmp_path)
    (tmp_path / ".recall").mkdir()
    (tmp_path / ".recall" / ".capture-paused").write_text("")
    monkeypatch.setattr(
        harness_opencode, "export_events",
        lambda sid: harness_opencode.events_from_export(export_doc()))
    opencode_capture.capture_session(cwd, "ses_abc123")
    assert not (tmp_path / ".recall" / "history.md").exists()


def test_capture_auto_saves_context_when_configured(tmp_path, monkeypatch):
    cwd = str(tmp_path)
    (tmp_path / "recall.config.json").write_text(
        json.dumps({"auto_save_context": "on_end"}), encoding="utf-8")
    events = harness_opencode.events_from_export(export_doc())
    monkeypatch.setattr(harness_opencode, "export_events", lambda sid: events)
    monkeypatch.setattr(harness_opencode, "collect_events",
                        lambda cwd_: ("ses_abc123", events))
    opencode_capture.capture_session(cwd, "ses_abc123")
    ctx = (tmp_path / ".recall" / "context.md").read_text(encoding="utf-8")
    assert GOAL in ctx


# ------------------------------------------------------------ make_context

def test_make_context_opencode_harness(tmp_path, monkeypatch):
    events = harness_opencode.events_from_export(export_doc())
    monkeypatch.setattr(harness_opencode, "collect_events",
                        lambda cwd: ("ses_abc123", events))
    assert make_context.run(str(tmp_path), quiet=True, harness="opencode") == 0
    ctx = (tmp_path / ".recall" / "context.md").read_text(encoding="utf-8")
    assert "## 🎯 Goal" in ctx and GOAL in ctx
    assert "pytest -q" in ctx  # commands survive the canonical tool names


def test_make_context_opencode_no_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(harness_opencode, "collect_events",
                        lambda cwd: (None, []))
    assert make_context.run(str(tmp_path), quiet=True, harness="opencode") == 1
    assert not (tmp_path / ".recall" / "context.md").exists()


# --------------------------------------------------------------- installer

def _install_paths(root):
    return (root / ".opencode" / "plugins" / "recall.ts",
            root / ".opencode" / "commands" / "recall-save.md",
            root / "opencode.json")


def test_install_writes_files_and_config(tmp_path):
    assert install.install_opencode(tmp_path) == 0
    plugin, command, cfg_path = _install_paths(tmp_path)
    plugin_text = plugin.read_text(encoding="utf-8")
    assert install.MARKER in plugin_text
    assert install.SCRIPTS_DIR.as_posix() in plugin_text
    assert "__RECALL_SCRIPTS__" not in plugin_text
    command_text = command.read_text(encoding="utf-8")
    assert install.MARKER in command_text
    assert "--harness opencode" in command_text
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["instructions"] == [install.CONTEXT_INSTRUCTION]


def test_install_is_idempotent_and_preserves_config(tmp_path):
    (tmp_path / "opencode.json").write_text(
        json.dumps({"model": "anthropic/claude", "instructions": ["AGENTS.md"]}),
        encoding="utf-8")
    assert install.install_opencode(tmp_path) == 0
    assert install.install_opencode(tmp_path) == 0
    cfg = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert cfg["model"] == "anthropic/claude"
    assert cfg["instructions"] == ["AGENTS.md", install.CONTEXT_INSTRUCTION]


def test_install_refuses_to_clobber_foreign_files(tmp_path):
    plugin, _command, _cfg = _install_paths(tmp_path)
    plugin.parent.mkdir(parents=True)
    plugin.write_text("my own plugin", encoding="utf-8")
    assert install.install_opencode(tmp_path) == 1
    assert plugin.read_text(encoding="utf-8") == "my own plugin"


def test_install_leaves_malformed_config_untouched(tmp_path):
    (tmp_path / "opencode.json").write_text("{oops", encoding="utf-8")
    assert install.install_opencode(tmp_path) == 1
    assert (tmp_path / "opencode.json").read_text(encoding="utf-8") == "{oops"
    plugin, _command, _cfg = _install_paths(tmp_path)
    assert plugin.exists()  # the rest of the install still went through


def test_uninstall_removes_only_what_was_generated(tmp_path):
    (tmp_path / "opencode.json").write_text(
        json.dumps({"instructions": ["AGENTS.md"]}), encoding="utf-8")
    install.install_opencode(tmp_path)
    assert install.uninstall_opencode(tmp_path) == 0
    plugin, command, cfg_path = _install_paths(tmp_path)
    assert not plugin.exists() and not command.exists()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["instructions"] == ["AGENTS.md"]


def test_uninstall_leaves_foreign_files_alone(tmp_path):
    plugin, _command, _cfg = _install_paths(tmp_path)
    plugin.parent.mkdir(parents=True)
    plugin.write_text("my own plugin", encoding="utf-8")
    assert install.uninstall_opencode(tmp_path) == 1
    assert plugin.read_text(encoding="utf-8") == "my own plugin"
