from pathlib import Path

from gcode.config import (
    load_config,
    resolve_auto_approve,
    resolve_bash_timeout,
    resolve_model,
    resolve_system_prompt,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".gcoderc"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_config_parses_values(tmp_path):
    _write(
        tmp_path,
        "# comment\n"
        "model = qwen/qwen3-coder:free\n"
        "auto_approve = true\n"
        "bash_timeout = 120\n"
        'system_prompt = "Custom prompt here"\n',
    )
    cfg = load_config(str(tmp_path))
    assert cfg["model"] == "qwen/qwen3-coder:free"
    assert cfg["auto_approve"] is True
    assert cfg["bash_timeout"] == 120
    assert cfg["system_prompt"] == "Custom prompt here"


def test_load_config_missing_file_is_empty(tmp_path):
    assert load_config(str(tmp_path)) == {}


def test_load_config_ignores_garbage_lines(tmp_path):
    _write(tmp_path, "not a valid line\n\n= no key\n# just a comment\n")
    assert load_config(str(tmp_path)) == {}


def test_resolve_model_precedence_cli_wins():
    cfg = {"model": "from-config"}
    assert resolve_model(cfg, "from-cli", "from-env") == "from-cli"
    assert resolve_model(cfg, None, "from-env") == "from-env"
    assert resolve_model(cfg, None, None) == "from-config"
    assert resolve_model({}, None, None) is None


def test_resolve_auto_approve_flag_wins():
    assert resolve_auto_approve({"auto_approve": False}, True) is True
    assert resolve_auto_approve({"auto_approve": True}, False) is True
    assert resolve_auto_approve({"auto_approve": False}, False) is False
    assert resolve_auto_approve({}, False) is False


def test_resolve_bash_timeout_config_wins():
    assert resolve_bash_timeout({"bash_timeout": 60}, 300) == 60
    assert resolve_bash_timeout({"bash_timeout": 0}, 300) == 300
    assert resolve_bash_timeout({}, 300) == 300


def test_resolve_system_prompt_config_wins():
    assert resolve_system_prompt({"system_prompt": "Custom"}, "default") == "Custom"
    assert resolve_system_prompt({"system_prompt": "   "}, "default") == "default"
    assert resolve_system_prompt({}, "default") == "default"
