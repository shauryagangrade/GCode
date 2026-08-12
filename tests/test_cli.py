from unittest.mock import Mock, patch

from gcode import __version__
from gcode.cli import _cmd_diff, _cmd_version, _print_help


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


def test_cmd_version_prints_installed_version():
    ui = Mock()
    _cmd_version(ui)

    ui.info.assert_called_once_with(f"GCode v{__version__}")


def test_help_lists_version_command():
    ui = Mock()
    _print_help(ui)

    help_text = ui.info.call_args.args[0]
    assert "/version" in help_text
    assert "installed GCode version" in help_text
