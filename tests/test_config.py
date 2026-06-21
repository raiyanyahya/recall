import json

from config import DEFAULTS, load_config


def _write(tmp_path, obj):
    (tmp_path / "recall.config.json").write_text(json.dumps(obj), encoding="utf-8")


def test_wrong_typed_values_fall_back_to_defaults(tmp_path):
    _write(tmp_path, {
        "output_dir": 123,              # must be str
        "summary_sentences": "lots",    # must be int
        "max_input_chars": -5,          # must be a positive int
        "redact": "yes",                # must be a real bool
        "capture_history": 1,           # int is not bool -> rejected
    })
    cfg = load_config(str(tmp_path))
    assert cfg["output_dir"] == DEFAULTS["output_dir"]
    assert cfg["summary_sentences"] == DEFAULTS["summary_sentences"]
    assert cfg["max_input_chars"] == DEFAULTS["max_input_chars"]
    assert cfg["redact"] is True
    assert cfg["capture_history"] is True


def test_valid_overrides_apply(tmp_path):
    _write(tmp_path, {
        "output_dir": "memory",
        "summary_sentences": 3,
        "redact": False,
        "auto_save_context": "on_end",
    })
    cfg = load_config(str(tmp_path))
    assert cfg["output_dir"] == "memory"
    assert cfg["summary_sentences"] == 3
    assert cfg["redact"] is False
    assert cfg["auto_save_context"] == "on_end"


def test_unknown_keys_ignored(tmp_path):
    _write(tmp_path, {"output_dir": "ok", "bogus_key": "x"})
    cfg = load_config(str(tmp_path))
    assert cfg["output_dir"] == "ok"
    assert "bogus_key" not in cfg


def test_missing_or_malformed_is_defaults(tmp_path):
    assert load_config(str(tmp_path)) == DEFAULTS          # no file
    (tmp_path / "recall.config.json").write_text("{not valid", encoding="utf-8")
    assert load_config(str(tmp_path)) == DEFAULTS          # malformed JSON
    (tmp_path / "recall.config.json").write_text("[1,2,3]", encoding="utf-8")
    assert load_config(str(tmp_path)) == DEFAULTS          # JSON but not an object
