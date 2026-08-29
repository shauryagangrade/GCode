import os
import sys
from unittest.mock import patch

import pytest
from gcode.tools import _grep_python, edit_file, grep, list_dir, read_file, write_file


def test_edit_file_unique(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "f.txt"
    p.write_text("hello world\n")
    out = edit_file.invoke({"path": str(p), "old_string": "world", "new_string": "there"})
    assert "Edited" in out
    assert p.read_text() == "hello there\n"


def test_edit_file_ambiguous(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "f.txt"
    p.write_text("a a a\n")
    out = edit_file.invoke({"path": str(p), "old_string": "a", "new_string": "b"})
    assert "found 3 times" in out


def test_edit_file_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = edit_file.invoke({"path": "no_such_file.txt", "old_string": "x", "new_string": "y"})
    assert "File not found" in out


def test_list_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    out = list_dir.invoke({"path": "."})
    assert "a.txt" in out
    assert "sub/" in out


def test_grep(tmp_path):
    (tmp_path / "a.txt").write_text("needle in hay\n")
    (tmp_path / "b.txt").write_text("nothing here\n")
    out = grep.invoke({"pattern": "needle", "path": str(tmp_path)})
    assert "needle in hay" in out


def test_grep_no_matches(tmp_path):
    (tmp_path / "a.txt").write_text("nothing here\n")
    out = grep.invoke({"pattern": "needle", "path": str(tmp_path)})
    assert "No matches" in out


def test_grep_ignore_case(tmp_path):
    (tmp_path / "a.txt").write_text("Needle in mixed case\n")
    out = grep.invoke({"pattern": "needle", "path": str(tmp_path), "ignore_case": True})
    assert "Needle in mixed case" in out


def test_grep_falls_back_without_grep_binary(tmp_path):
    (tmp_path / "a.txt").write_text("needle in hay\n")
    (tmp_path / "b.txt").write_text("nothing here\n")
    with patch("gcode.tools.shutil.which", return_value=None):
        out = grep.invoke({"pattern": "needle", "path": str(tmp_path)})
    assert "needle in hay" in out
    assert "b.txt" not in out


def test_grep_python_fallback_directly(tmp_path):
    (tmp_path / "a.txt").write_text("line one\nneedle here\nline three\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("no match in this file\n")
    out = _grep_python("needle", str(tmp_path), "*")
    assert "a.txt:2:needle here" in out
    assert "b.py" not in out


def test_grep_python_fallback_glob_filter(tmp_path):
    (tmp_path / "a.txt").write_text("needle\n")
    (tmp_path / "b.py").write_text("needle\n")
    out = _grep_python("needle", str(tmp_path), "*.py")
    assert "b.py" in out
    assert "a.txt" not in out


def test_grep_python_fallback_ignore_case(tmp_path):
    (tmp_path / "a.txt").write_text("Needle in mixed case\n")
    out = _grep_python("needle", str(tmp_path), "*", ignore_case=True)
    assert "Needle in mixed case" in out


def test_grep_python_fallback_single_file(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("needle in a single file\n")
    out = _grep_python("needle", str(p), "*")
    assert "needle in a single file" in out


def test_grep_python_fallback_invalid_regex(tmp_path):
    out = _grep_python("(unclosed", str(tmp_path), "*")
    assert "Invalid regex" in out
    assert "(unclosed" in out
    assert "Check the pattern syntax" in out
    assert "literal backslash" in out


def test_grep_python_fallback_path_not_found():
    out = _grep_python("needle", "/no/such/path", "*")
    assert "Path not found" in out


def test_grep_python_fallback_skips_binary_files(tmp_path):
    (tmp_path / "bin.dat").write_bytes(b"\xff\xfe\x00needle\x00")
    (tmp_path / "text.txt").write_text("needle in text\n")
    out = _grep_python("needle", str(tmp_path), "*")
    assert "text.txt" in out
    assert "bin.dat" not in out


def test_execute_bash_rejects_non_interactive_eof():
    from gcode.tools import execute_bash

    with patch("builtins.input", side_effect=EOFError):
        out = execute_bash.invoke({"command": "echo hi"})
    assert out == (
        "Command rejected: no terminal available (non-interactive). Run with --yes to auto-approve."
    )


def test_execute_bash_cancels_on_keyboard_interrupt():
    from gcode.tools import execute_bash

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        out = execute_bash.invoke({"command": "echo hi"})
    assert out == "Command execution cancelled by user."


def test_execute_bash_cancels_when_subprocess_interrupted():
    """Ctrl+C while the command is actually running cancels just that command.

    The interrupt arrives from ``subprocess.run`` (the prompt was already
    approved), and must return a cancelled result instead of killing the
    whole session.
    """
    from gcode.tools import AUTO_APPROVE, execute_bash, set_auto_approve

    set_auto_approve(True)
    try:
        with patch("gcode.tools.subprocess.run", side_effect=KeyboardInterrupt):
            out = execute_bash.invoke({"command": "sleep 100"})
        assert out == "Command execution cancelled by user."
    finally:
        set_auto_approve(AUTO_APPROVE)


def test_execute_bash_rejects_non_yes_answer():
    from gcode.tools import execute_bash

    with patch("builtins.input", return_value="n"):
        out = execute_bash.invoke({"command": "echo hi"})
    assert out == "Command execution cancelled by user."


def test_execute_bash_auto_approve_skips_prompt(tmp_path):
    from gcode.tools import AUTO_APPROVE, execute_bash, set_auto_approve

    set_auto_approve(True)
    try:
        with patch("builtins.input", side_effect=AssertionError("must not prompt")):
            out = execute_bash.invoke({"command": "echo auto-approved"})
        assert "auto-approved" in out
    finally:
        set_auto_approve(AUTO_APPROVE)


def test_execute_bash_windows_missing_bash_returns_clear_error():
    from gcode.tools import AUTO_APPROVE, execute_bash, set_auto_approve

    set_auto_approve(True)
    try:
        with (
            patch("gcode.tools.os.name", "nt"),
            patch("gcode.tools.shutil.which", return_value=None),
        ):
            out = execute_bash.invoke({"command": "echo hi"})
    finally:
        set_auto_approve(AUTO_APPROVE)
    assert "bash not found on native Windows" in out


def test_execute_bash_windows_runs_bash_explicitly(tmp_path, monkeypatch):
    """On Windows, shell=True would invoke cmd.exe; bash must run explicitly."""
    from gcode.tools import AUTO_APPROVE, execute_bash, set_auto_approve

    monkeypatch.chdir(tmp_path)
    set_auto_approve(True)
    try:
        with (
            patch("gcode.tools.os.name", "nt"),
            patch("gcode.tools.shutil.which", return_value="C:/Program Files/Git/bin/bash.exe"),
            patch("gcode.tools.subprocess.run") as run,
        ):
            run.return_value.returncode = 0
            run.return_value.stdout = "hi from bash\n"
            run.return_value.stderr = ""
            out = execute_bash.invoke({"command": "echo hi"})
    finally:
        set_auto_approve(AUTO_APPROVE)
    assert "hi from bash" in out
    cmd, kwargs = run.call_args
    assert cmd[0] == ["C:/Program Files/Git/bin/bash.exe", "-c", "echo hi"]
    assert kwargs.get("shell") is not True


def test_grep_passes_include_as_one_argument():
    """The glob must stay attached to --include, as --include=<glob>.

    On Windows the grep on PATH is usually Git for Windows' MSYS build, whose
    runtime glob-expands a bare "*" argument against the current directory
    before grep sees it -- so `--include", "*"` becomes `--include <some file
    in cwd>` and a search of any other directory matches nothing.

    Both spellings behave identically where that runtime is not involved, so
    this asserts the command shape rather than the result: on a Linux runner a
    revert would otherwise stay green.
    """
    with (
        patch("gcode.tools.shutil.which", return_value="/usr/bin/grep"),
        patch("gcode.tools.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""

        grep.invoke({"pattern": "needle", "path": ".", "glob": "*.py"})

    cmd = run.call_args[0][0]
    assert "--include=*.py" in cmd
    assert "--include" not in cmd, "the glob must not be a separate argument"


def test_grep_include_defaults_to_everything():
    """The default glob is still passed, so behaviour is unchanged."""
    with (
        patch("gcode.tools.shutil.which", return_value="/usr/bin/grep"),
        patch("gcode.tools.subprocess.run") as run,
    ):
        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = ""

        grep.invoke({"pattern": "needle", "path": "."})

    assert "--include=*" in run.call_args[0][0]


def test_grep_passes_H_for_consistent_single_file_output():
    """-H must stay in the flags so single-file output is never prefixed-less.

    Without it GNU grep drops the filename prefix for a single-file target
    while the pure-Python fallback always prints it, making `grep` return
    differently shaped output depending on whether a grep binary is installed.
    """
    with (
        patch("gcode.tools.shutil.which", return_value="/usr/bin/grep"),
        patch("gcode.tools.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""

        grep.invoke({"pattern": "needle", "path": "."})

    assert "-rnIH" in run.call_args[0][0]


def test_grep_filters_by_glob(tmp_path):
    """End-to-end: the glob still selects files rather than being ignored."""
    (tmp_path / "a.txt").write_text("needle in text\n")
    (tmp_path / "b.py").write_text("needle in python\n")

    out = grep.invoke({"pattern": "needle", "path": str(tmp_path), "glob": "*.py"})

    assert "needle in python" in out
    assert "needle in text" not in out


# -- workspace boundary -------------------------------------------------------


class _FakeStdIn:
    """Stand-in for sys.stdin to control tty detection."""

    def __init__(self, interactive: bool):
        self._interactive = interactive

    def isatty(self) -> bool:
        return self._interactive


def _outside_file(tmp_path):
    """A file that resolves outside the workspace (cwd == tmp_path)."""
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret content\n")
    return outside


def test_file_tools_reject_outside_workspace_non_tty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=False))

    out = read_file.invoke({"path": str(_outside_file(tmp_path))})
    assert "Refusing to access" in out
    assert "outside workspace" in out


def test_file_tools_reject_outside_workspace_interactive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=True))

    with patch("builtins.input", return_value="n"):
        out = read_file.invoke({"path": str(_outside_file(tmp_path))})
    assert "Refusing to access" in out


def test_file_tools_allow_confirmed_outside_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=True))

    with patch("builtins.input", return_value="y"):
        out = read_file.invoke({"path": str(_outside_file(tmp_path))})
    assert "secret content" in out


def test_write_file_outside_workspace_rejected_non_tty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=False))

    outside = tmp_path.parent / "outside_write.txt"
    out = write_file.invoke({"path": str(outside), "content": "boom"})
    assert "Refusing to access" in out
    assert not outside.exists()


def test_auto_approve_allows_outside_workspace(tmp_path, monkeypatch):
    from gcode.tools import AUTO_APPROVE, set_auto_approve

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=False))

    set_auto_approve(True)
    try:
        out = read_file.invoke({"path": str(_outside_file(tmp_path))})
    finally:
        set_auto_approve(AUTO_APPROVE)
    assert "secret content" in out


def test_workspace_boundary_resolves_inside_and_dotdot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=False))

    (tmp_path / "inside.txt").write_text("ok\n")
    assert "ok" in read_file.invoke({"path": "inside.txt"})

    out = read_file.invoke({"path": "../escaped.txt"})
    assert "Refusing to access" in out


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks not supported")
def test_workspace_boundary_blocks_symlink_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdIn(interactive=False))

    target = tmp_path.parent / "target.txt"
    target.write_text("secret\n")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    out = read_file.invoke({"path": str(link)})
    assert "Refusing to access" in out
