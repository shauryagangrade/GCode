from unittest.mock import Mock, patch

import pytest
from gcode import __version__
from gcode.cli import (
    _cmd_diff,
    _cmd_skill,
    _cmd_skill_import,
    _cmd_skills,
    _cmd_status,
    _cmd_version,
    _print_help,
)


def test_cmd_diff_prints_repository_changes():
    ui = Mock()
    git_diff = Mock()
    git_diff.invoke.return_value = "diff output"
    with patch("gcode.cli.tool_module.git_diff", git_diff):
        _cmd_diff(ui)

    ui.print.assert_called_once_with("diff output", markup=False, highlight=False)


def test_help_lists_diff_command():
    ui = Mock()
    _print_help(ui)

    help_text = ui.info.call_args.args[0]
    assert "/diff" in help_text
    assert "staged and unstaged git changes" in help_text


def test_cmd_status_prints_repository_status():
    ui = Mock()
    git_status = Mock()
    git_status.invoke.return_value = " M gcode/cli.py"
    with patch("gcode.cli.tool_module.git_status", git_status):
        _cmd_status(ui)

    git_status.invoke.assert_called_once_with({})
    ui.print.assert_called_once_with(" M gcode/cli.py", markup=False, highlight=False)


def test_cmd_version_prints_installed_version():
    ui = Mock()
    _cmd_version(ui)

    ui.info.assert_called_once_with(f"GCode v{__version__}")


def test_help_lists_status_command():
    ui = Mock()
    _print_help(ui)

    help_text = ui.info.call_args.args[0]
    assert "/status" in help_text
    assert "git status" in help_text


def test_help_lists_version_command():
    ui = Mock()
    _print_help(ui)

    help_text = ui.info.call_args.args[0]
    assert "/version" in help_text
    assert "installed GCode version" in help_text


def test_help_has_categorized_groups():
    ui = Mock()
    _print_help(ui)

    help_text = ui.info.call_args.args[0]
    assert "General" in help_text
    assert "Model" in help_text
    assert "Session" in help_text
    assert "Git" in help_text
    assert "/help" in help_text
    assert "/models" in help_text
    assert "/history" in help_text
    assert "/diff" in help_text


def test_report_no_models_network_error_path():
    from gcode.cli import _report_no_models

    ui = Mock()
    catalog_err = "Could not fetch the OpenRouter model list: network error."
    with patch("gcode.cli.list_free_models", return_value=([], catalog_err)):
        _report_no_models(ui)

    assert ui.error.call_args.args[0] == catalog_err
    assert "Ollama" in ui.info.call_args.args[0]


def test_report_no_models_ollama_running_no_models():
    from gcode.cli import _report_no_models

    ui = Mock()
    with (
        patch("gcode.cli.list_free_models", return_value=([], None)),
        patch("gcode.cli.is_ollama_running", return_value=True),
    ):
        _report_no_models(ui)

    assert "No models found locally" in ui.error.call_args.args[0]
    assert "/pull" in ui.info.call_args.args[0]


def test_report_no_models_neither_source():
    from gcode.cli import _report_no_models

    ui = Mock()
    with (
        patch("gcode.cli.list_free_models", return_value=([], None)),
        patch("gcode.cli.is_ollama_running", return_value=False),
    ):
        _report_no_models(ui)

    assert "No model source is reachable" in ui.error.call_args.args[0]
    assert "Ollama" in ui.info.call_args.args[0]


def test_help_lists_cwd_flag(capsys):

    from gcode.cli import main

    with patch("sys.argv", ["gcode", "--help"]), pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert "--cwd" in capsys.readouterr().out


class _Sentinel(Exception):
    """Raised from the first call after the chdir, to stop main() there."""


def test_cwd_changes_directory_before_config_is_loaded(tmp_path, monkeypatch):
    """The chdir must land before anything reads the working directory.

    .gcoderc discovery, the banner and every tool resolve against it, so a
    chdir performed later would leave them describing different projects.
    load_env is the first call after it, so raising there proves the ordering
    without running the interactive session.
    """
    import os

    from gcode.cli import main

    start = os.getcwd()
    seen = {}

    def _record():
        seen["cwd"] = os.getcwd()
        raise _Sentinel

    monkeypatch.setattr("gcode.cli.load_env", _record)
    monkeypatch.setattr("sys.argv", ["gcode", "--cwd", str(tmp_path)])
    try:
        with pytest.raises(_Sentinel):
            main()
    finally:
        os.chdir(start)

    assert os.path.realpath(seen["cwd"]) == os.path.realpath(str(tmp_path))


def test_without_cwd_the_directory_is_untouched(monkeypatch):
    import os

    from gcode.cli import main

    start = os.getcwd()
    seen = {}

    def _record():
        seen["cwd"] = os.getcwd()
        raise _Sentinel

    monkeypatch.setattr("gcode.cli.load_env", _record)
    monkeypatch.setattr("sys.argv", ["gcode"])
    try:
        with pytest.raises(_Sentinel):
            main()
    finally:
        os.chdir(start)

    assert seen["cwd"] == start


def test_cwd_that_does_not_exist_exits_two(tmp_path, capsys, monkeypatch):
    """A bad --cwd is user input: one line on stderr, exit 2, no traceback."""
    import os

    from gcode.cli import main

    missing = tmp_path / "no-such-project"
    start = os.getcwd()
    monkeypatch.setattr("sys.argv", ["gcode", "--cwd", str(missing)])
    try:
        with pytest.raises(SystemExit) as exc:
            main()
    finally:
        os.chdir(start)

    assert exc.value.code == 2
    stderr = capsys.readouterr().err
    assert "--cwd" in stderr
    assert "Traceback" not in stderr


def test_help_lists_skills_commands():
    ui = Mock()
    _print_help(ui)

    help_text = ui.info.call_args.args[0]
    assert "Skills" in help_text
    assert "/skills" in help_text
    assert "/skill <name>" in help_text
    assert "/skill import <package>" in help_text


def test_cmd_skills_reports_when_none_found(tmp_path, monkeypatch):
    from gcode import skills as skills_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_module, "CLAUDE_SKILLS_DIR", tmp_path / "nonexistent-claude-dir")
    ui = Mock()
    _cmd_skills(ui)

    assert "No skills found" in ui.info.call_args.args[0]


def test_cmd_skills_lists_discovered_skills(tmp_path, monkeypatch):
    from gcode import skills as skills_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_module, "CLAUDE_SKILLS_DIR", tmp_path / "nonexistent-claude-dir")
    skills_dir = tmp_path / ".gcode" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "foo.md").write_text("# Foo\nDoes stuff.", encoding="utf-8")

    ui = Mock()
    _cmd_skills(ui)

    printed = ui.print.call_args.args[0]
    assert "Available skills:" in printed
    assert "foo" in printed
    assert "[project]" in printed
    assert "Foo" in printed


def test_cmd_skills_truncates_long_descriptions_to_one_line(tmp_path, monkeypatch):
    from gcode import skills as skills_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_module, "CLAUDE_SKILLS_DIR", tmp_path / "nonexistent-claude-dir")
    skills_dir = tmp_path / ".gcode" / "skills"
    skills_dir.mkdir(parents=True)
    long_description = ("word " * 60).strip()
    (skills_dir / "long.md").write_text(long_description, encoding="utf-8")

    ui = Mock()
    _cmd_skills(ui)

    printed = ui.print.call_args.args[0]
    line = next(line for line in printed.splitlines() if "long" in line)
    # Markup tags inflate the raw string; untruncated it would be ~330 chars.
    assert len(line) <= 160
    assert line.rstrip().endswith("…")
    assert long_description not in printed


def test_cmd_skill_with_no_argument_shows_usage():
    ui = Mock()
    _cmd_skill("", [], ui)

    assert "Usage:" in ui.info.call_args.args[0]


def test_cmd_skill_unknown_name_reports_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ui = Mock()
    _cmd_skill("nonexistent", [], ui)

    assert "Unknown skill" in ui.info.call_args.args[0]


def test_cmd_skill_activates_by_extending_system_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skills_dir = tmp_path / ".gcode" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "foo.md").write_text("# Foo\nExtra instructions.", encoding="utf-8")

    system_message = Mock(content="base prompt")
    messages = [system_message]
    ui = Mock()
    _cmd_skill("foo", messages, ui)

    assert "base prompt" in system_message.content
    assert "Extra instructions." in system_message.content
    assert "Activated skill 'foo'" in ui.info.call_args.args[0]


def test_cmd_skill_import_with_no_package_shows_usage():
    ui = Mock()
    _cmd_skill("import ", [], ui)

    assert "Usage: /skill import" in ui.info.call_args.args[0]


def test_cmd_skill_import_dispatches_after_approval():
    ui = Mock()
    with (
        patch("gcode.cli.tool_module.is_auto_approve", return_value=False),
        patch("builtins.input", return_value="y"),
        patch("gcode.cli.skills_module.import_skill", return_value=["imported"]) as mock_import,
    ):
        _cmd_skill("import some-pkg", [], ui)

    mock_import.assert_called_once()
    assert mock_import.call_args.args[0] == "some-pkg"
    assert "Imported skill(s)" in ui.info.call_args.args[0]


def test_cmd_skill_import_cancelled_when_not_approved():
    ui = Mock()
    with (
        patch("gcode.cli.tool_module.is_auto_approve", return_value=False),
        patch("builtins.input", return_value="n"),
        patch("gcode.cli.skills_module.import_skill") as mock_import,
    ):
        _cmd_skill("import some-pkg", [], ui)

    mock_import.assert_not_called()
    assert "cancelled" in ui.info.call_args.args[0]


def test_cmd_skill_import_skips_prompt_when_auto_approved():
    ui = Mock()
    with (
        patch("gcode.cli.tool_module.is_auto_approve", return_value=True),
        patch("builtins.input", side_effect=AssertionError("should not prompt")),
        patch("gcode.cli.skills_module.import_skill", return_value=["x"]) as mock_import,
    ):
        _cmd_skill("import some-pkg", [], ui)

    mock_import.assert_called_once()


def test_cmd_skill_import_reports_runtime_error():
    ui = Mock()
    with (
        patch("gcode.cli.tool_module.is_auto_approve", return_value=True),
        patch("gcode.cli.skills_module.import_skill", side_effect=RuntimeError("npx boom")),
    ):
        _cmd_skill_import("some-pkg", ui)

    ui.error.assert_called_once_with("npx boom")


def test_cmd_skill_import_reports_oserror_without_crashing():
    ui = Mock()
    with (
        patch("gcode.cli.tool_module.is_auto_approve", return_value=True),
        patch(
            "gcode.cli.skills_module.import_skill",
            side_effect=OSError(13, "Permission denied"),
        ),
    ):
        _cmd_skill_import("some-pkg", ui)

    assert "Permission denied" in ui.error.call_args.args[0]


def test_cwd_pointing_at_a_file_exits_two(tmp_path, capsys, monkeypatch):
    import os

    from gcode.cli import main

    target = tmp_path / "notadir.txt"
    target.write_text("x\n")
    start = os.getcwd()
    monkeypatch.setattr("sys.argv", ["gcode", "--cwd", str(target)])
    try:
        with pytest.raises(SystemExit) as exc:
            main()
    finally:
        os.chdir(start)

    assert exc.value.code == 2
