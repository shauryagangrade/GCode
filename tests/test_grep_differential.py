"""Differential tests: `_grep_python` against a real `grep` on one corpus.

`_grep_python` is the fallback used where no `grep` binary exists, so the two
implementations serve the same calls and are only ever exercised separately.
Asserting each against hand-written expected strings lets them drift: regex
flavour, glob handling, case folding and binary detection are all places where
"looks right" and "matches GNU grep" are different claims.

These build one corpus and require both to agree on it.

The tests are gated on `grep` being **present**, not on the platform. Git for
Windows ships GNU grep, so gating on `sys.platform` would skip exactly where
the fallback is the default code path and divergence matters most. Where grep
genuinely is absent there is nothing to compare and the tests skip.
"""

import os
import re
import shutil
import subprocess

import pytest
from gcode.tools import _grep_python

_LINE = re.compile(r"^(.*?):(\d+):(.*)$")
grep_bin = shutil.which("grep")
requires_grep = pytest.mark.skipif(grep_bin is None, reason="no grep binary on PATH")

_grep_version = (
    subprocess.run([grep_bin, "--version"], capture_output=True, text=True, check=False).stdout
    if grep_bin
    else ""
)
requires_gnu_grep = pytest.mark.skipif(
    "GNU grep" not in _grep_version,
    reason="GNU grep only: BSD grep keeps the filename prefix on a single-file target",
)


@pytest.fixture
def corpus(tmp_path):
    """Text, nested dirs, a binary file, and files in and out of a glob."""
    (tmp_path / "top.txt").write_text("needle at the top\nplain line\n", encoding="utf-8")
    (tmp_path / "top.py").write_text("# needle in python\nvalue = 1\n", encoding="utf-8")
    (tmp_path / "shouty.txt").write_text("NEEDLE shouting\n", encoding="utf-8")

    nested = tmp_path / "sub" / "deeper"
    nested.mkdir(parents=True)
    (nested / "buried.txt").write_text("needle buried deep\n", encoding="utf-8")
    (nested / "buried.py").write_text("# needle buried in python\n", encoding="utf-8")

    # NUL in the first chunk: both implementations must skip this.
    (tmp_path / "blob.bin").write_bytes(b"needle\x00 hidden in binary\n")

    (tmp_path / "quiet.txt").write_text("nothing of interest\n", encoding="utf-8")
    return tmp_path


def _reference(pattern, path, glob="*", ignore_case=False):
    """Run the system grep the way the grep tool does, as a set of matches."""
    # -H so a single-file target still prints its name. GNU grep drops the
    # prefix when there is only one input; _grep_python always emits it. That
    # divergence is real and is pinned in its own test below -- forcing the
    # prefix here keeps *this* comparison about which lines matched.
    flags = ["-rnIH"]
    if ignore_case:
        flags.append("-i")
    # --include=<glob> as one argument: a bare "*" would be glob-expanded by
    # the MSYS runtime against the cwd before grep ever sees it.
    cmd = [grep_bin, *flags, f"--include={glob}", "-e", pattern, str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode in (0, 1), result.stderr
    return _normalise(result.stdout, path)


def _actual(pattern, path, glob="*", ignore_case=False):
    out = _grep_python(pattern, str(path), glob, ignore_case)
    if out.startswith("No matches for "):
        return set()
    return _normalise(out, path)


def _normalise(output, root):
    """Reduce grep output to {(relative posix path, lineno, text)}.

    Both sides are asked the same question, but not in the same words: grep
    joins its argument to each entry with a forward slash while os.walk uses
    the platform separator, so the raw strings differ on Windows even when the
    matches are identical. Comparing the triple keeps the assertion about
    *which lines matched*, which is the thing that can actually drift.
    """
    matches = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        # Not split(":", 2): a Windows path carries its own colon after the
        # drive letter. Anchor on the line number instead -- the first
        # ":<digits>:" that leaves a parsable path behind it.
        parsed = _LINE.match(line)
        assert parsed, f"unparsable grep line: {line!r}"
        filepath, lineno, text = parsed.groups()
        relative = os.path.relpath(filepath, str(root)).replace(os.sep, "/")
        matches.add((relative, int(lineno), text))
    return matches


@requires_grep
def test_plain_regex_agrees(corpus):
    assert _actual("needle", corpus) == _reference("needle", corpus)


@requires_grep
def test_plain_regex_finds_the_expected_files(corpus):
    """Anchor the comparison, so both agreeing on nothing cannot pass."""
    found = {path for path, _, _ in _actual("needle", corpus)}

    assert found == {"top.txt", "top.py", "sub/deeper/buried.txt", "sub/deeper/buried.py"}


@requires_grep
def test_ignore_case_agrees(corpus):
    assert _actual("needle", corpus, ignore_case=True) == _reference(
        "needle", corpus, ignore_case=True
    )


@requires_grep
def test_ignore_case_picks_up_the_uppercase_line(corpus):
    sensitive = _actual("needle", corpus)
    insensitive = _actual("needle", corpus, ignore_case=True)

    assert ("shouty.txt", 1, "NEEDLE shouting") in insensitive
    assert insensitive > sensitive


@requires_grep
def test_glob_filter_agrees(corpus):
    assert _actual("needle", corpus, glob="*.py") == _reference("needle", corpus, glob="*.py")


@requires_grep
def test_glob_filter_actually_filters(corpus):
    found = {path for path, _, _ in _actual("needle", corpus, glob="*.py")}

    assert found == {"top.py", "sub/deeper/buried.py"}


@requires_grep
def test_no_match_agrees(corpus):
    pattern = "definitely-not-in-the-corpus"

    assert _actual(pattern, corpus) == _reference(pattern, corpus) == set()


@requires_grep
def test_binary_file_is_skipped_by_both(corpus):
    """grep -I skips it; _is_binary must reach the same verdict."""
    assert _actual("needle", corpus) == _reference("needle", corpus)
    assert not any(path.endswith(".bin") for path, _, _ in _actual("needle", corpus))


@requires_grep
def test_regex_metacharacters_agree(corpus):
    """Basic vs extended regex is the classic divergence between the two."""
    (corpus / "meta.txt").write_text("a1b\naXb\n", encoding="utf-8")

    for pattern in ("a[0-9]b", "^needle", "line$", "n..dle"):
        assert _actual(pattern, corpus) == _reference(pattern, corpus), pattern


@requires_grep
def test_single_file_target_agrees(corpus):
    target = corpus / "top.txt"

    assert _actual("needle", target) == _reference("needle", target)


@requires_grep
@requires_gnu_grep
def test_single_file_output_format_diverges(corpus):
    """A real difference this comparison surfaced -- recorded, not fixed here.

    Given one file rather than a directory, GNU grep drops the filename prefix
    and emits "1:needle at the top"; _grep_python always emits
    "<path>:1:needle at the top". So `grep(pattern, path="a.txt")` returns a
    different shape depending on whether a grep binary happens to be installed
    -- which is the class of drift #63 exists to catch.

    Pinned rather than fixed: aligning them changes the grep tool's output and
    is a call for the maintainer, not a drive-by in a test-only change. Adding
    -H to the tool's flags would do it.
    """
    target = corpus / "top.txt"

    python_side = _grep_python("needle", str(target), "*", False)
    binary_side = subprocess.run(
        [grep_bin, "-rnI", "--include=*", "-e", "needle", str(target)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout

    assert python_side.startswith(str(target))
    assert binary_side.startswith("1:")
