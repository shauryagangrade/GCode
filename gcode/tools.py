"""GCode agent tools: shell, filesystem, and git operations.

Each tool is decorated with ``@tool`` so the model receives a clean schema and
description. The model calls tools by name; :data:`TOOL_MAP` dispatches those
calls back to the right object.
"""

import fnmatch
import os
import re
import shutil
import subprocess

from langchain.tools import tool

# Whether to skip the interactive y/n confirmation for bash commands. Set from
# the CLI via :func:`set_auto_approve`.
AUTO_APPROVE = False

BASH_TIMEOUT = 300


def set_auto_approve(value: bool) -> None:
    global AUTO_APPROVE
    AUTO_APPROVE = value


def is_auto_approve() -> bool:
    """Return whether bash auto-approval is currently enabled.

    Read at call time so modules that imported the module (rather than the
    value) always see the latest setting.
    """
    return AUTO_APPROVE


@tool
def execute_bash(command: str) -> str:
    """Execute a bash command on the local machine and return its output.

    Requires interactive confirmation (y/n) before running unless auto-approve
    is enabled. In non-interactive environments (CI, Docker, pipes) the command
    is rejected rather than hanging or crashing; enable auto-approve to run.
    Returns combined stdout and stderr, and reports a non-zero exit code if the
    command fails.
    """
    if not AUTO_APPROVE:
        try:
            confirm = input(f"GCode wants to run: {command}\nApprove? (y/n): ")
        except EOFError:
            return (
                "Command rejected: no terminal available (non-interactive). "
                "Run with --yes to auto-approve."
            )
        except KeyboardInterrupt:
            return "Command execution cancelled by user."
        if confirm.strip().lower() != "y":
            return "Command execution cancelled by user."
    try:
        result = subprocess.run(  # nosec B602 — execute_bash is the tool's purpose; gated by y/n approval
            command, shell=True, capture_output=True, text=True, timeout=BASH_TIMEOUT, check=False
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {BASH_TIMEOUT}s: {command}"

    output = result.stdout.strip()
    if result.stderr.strip():
        output += ("\n" if output else "") + f"[stderr]\n{result.stderr.strip()}"
    if result.returncode != 0:
        output += ("\n" if output else "") + f"[exit code: {result.returncode}]"
    return output or "(no output)"


@tool
def read_file(path: str, max_lines: int = 2000) -> str:
    """Read a text file and return its contents.

    Args:
        path: Path to the file.
        max_lines: Maximum number of lines to return (default 2000); longer
            files are truncated with a note.
    """
    if not os.path.isfile(path):
        return f"File not found: {path}"
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        return f"Error reading {path}: {exc}"

    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]

    text = "".join(lines)
    if truncated:
        text += f"\n... [truncated at {max_lines} lines]"
    return text or "(empty file)"


@tool
def write_file(path: str, content: str, force: bool = False) -> str:
    """Create or overwrite a file with the given content.

    Refuses to overwrite an existing file unless force=True, to avoid silent
    data loss.

    Args:
        path: Destination path.
        content: Full text content to write.
        force: If True, overwrite an existing file.
    """
    if os.path.exists(path) and not force:
        return f"Refusing to overwrite existing file {path} (pass force=True to overwrite)."
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        return f"Error writing {path}: {exc}"
    size = len(content.encode("utf-8"))
    return f"Wrote {size} bytes to {path}"


@tool
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace text in a file using an exact string match.

    Errors if old_string is not found, or (when replace_all is False) if it
    appears more than once, to avoid ambiguous edits.

    Args:
        path: File to edit.
        old_string: Exact text to find.
        new_string: Replacement text.
        replace_all: If True, replace every occurrence.
    """
    if not os.path.isfile(path):
        return f"File not found: {path}"
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception as exc:
        return f"Error reading {path}: {exc}"

    count = text.count(old_string)
    if count == 0:
        return f"old_string not found in {path}."
    if count > 1 and not replace_all:
        return (
            f"old_string found {count} times in {path}; pass replace_all=True to "
            "replace all, or make old_string unique."
        )

    new_text = (
        text.replace(old_string, new_string, 1)
        if not replace_all
        else text.replace(old_string, new_string)
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
    except Exception as exc:
        return f"Error writing {path}: {exc}"
    return f"Edited {path} ({count} occurrence(s) replaced)."


@tool
def list_dir(path: str = ".") -> str:
    """List the contents of a directory.

    Args:
        path: Directory to list (default current directory).
    """
    if not os.path.isdir(path):
        return f"Not a directory: {path}"
    try:
        entries = sorted(os.listdir(path))
    except Exception as exc:
        return f"Error listing {path}: {exc}"
    if not entries:
        return f"(empty directory: {path})"
    lines = []
    for name in entries:
        full = os.path.join(path, name)
        marker = "/" if os.path.isdir(full) else ""
        lines.append(f"{name}{marker}")
    return "\n".join(lines)


@tool
def grep(
    pattern: str,
    path: str = ".",
    glob: str = "*",
    ignore_case: bool = False,
) -> str:
    """Search file contents for a pattern.

    Uses the system ``grep`` binary when available (fast, handles large
    trees well) and falls back to a pure-Python search otherwise, so this
    works on systems without ``grep`` on PATH (e.g. plain Windows).

    Args:
        pattern: Regex pattern to search for.
        path: Directory or file to search (default current directory).
        glob: Shell glob to limit which files are searched (default "*").
        ignore_case: Match upper- and lower-case variants (default False).
    """
    grep_bin = shutil.which("grep")
    if grep_bin:
        flags = ["-rnI"]
        if ignore_case:
            flags.append("-i")
        cmd = [grep_bin, *flags, "--include", glob, "-e", pattern, path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            return "grep timed out after 60s."
        if result.returncode == 1:
            return f"No matches for {pattern!r} in {path}."
        if result.returncode != 0:
            return f"grep error: {result.stderr.strip()}"
        return result.stdout.strip()

    return _grep_python(pattern, path, glob, ignore_case)


def _is_binary(filepath: str) -> bool:
    """Detect if a file is binary by checking for null bytes in the first chunk."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return True
    except OSError:
        pass
    return False


def _grep_python(pattern: str, path: str, glob: str, ignore_case: bool = False) -> str:
    """Pure-Python fallback for :func:`grep` when no ``grep`` binary exists.

    Walks ``path`` (or searches a single file), matching filenames against
    ``glob`` and lines against ``pattern`` as a regex. Best-effort: unreadable
    or binary-looking files are skipped rather than raising.
    """
    try:
        regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as exc:
        return (
            f"Invalid regex {pattern!r}: {exc}. "
            "Check the pattern syntax and escape special characters "
            "(for example, use '\\\\' for a literal backslash)."
        )

    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = []
        for root, _dirs, names in os.walk(path):
            for name in names:
                if fnmatch.fnmatch(name, glob):
                    files.append(os.path.join(root, name))
    else:
        return f"Path not found: {path}"

    matches = []
    for filepath in sorted(files):
        if _is_binary(filepath):
            continue
        try:
            with open(filepath, encoding="utf-8", errors="strict") as f:
                for lineno, line in enumerate(f, start=1):
                    if regex.search(line):
                        matches.append(f"{filepath}:{lineno}:{line.rstrip(chr(10))}")
        except (UnicodeDecodeError, OSError):
            # Skip binary or unreadable files, same as `grep -I`.
            continue

    if not matches:
        return f"No matches for {pattern!r} in {path}."
    return "\n".join(matches)


@tool
def git_status() -> str:
    """Show the working tree status of the current git repository."""
    return _git(["status", "--short"])


@tool
def git_diff(path: str | None = None) -> str:
    """Show staged and unstaged changes, optionally limited to a path.

    Args:
        path: Optional file or directory to limit the diff to.
    """
    cmd = ["diff"]
    if path:
        cmd.append(path)
    return _git(cmd)


@tool
def git_commit(message: str) -> str:
    """Stage all changes and create a commit with the given message.

    Args:
        message: Commit message.
    """
    added = _git(["add", "-A"])
    if added.startswith("git error"):
        return added
    return _git(["commit", "-m", message])


def _git(args: list) -> str:
    cmd = ["git"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return "git command timed out after 120s."
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        return f"git error: {err or out or 'unknown error'}"
    return out or "(no output)"


# Tools bound to the model, in the order they're declared.
ALL_TOOLS = [
    execute_bash,
    read_file,
    write_file,
    edit_file,
    list_dir,
    grep,
    git_status,
    git_diff,
    git_commit,
]

# name -> tool object, used to dispatch model tool calls.
TOOL_MAP = {t.name: t for t in ALL_TOOLS}
