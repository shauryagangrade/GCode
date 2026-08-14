from unittest.mock import Mock, patch

import pytest
from gcode import __version__
from gcode.cli import _cmd_diff, _cmd_status, _cmd_version, _print_help


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
