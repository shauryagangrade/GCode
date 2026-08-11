import os
from unittest.mock import patch

from gcode.tools import _grep_python, edit_file, grep, list_dir


def test_edit_file_unique():
    d = "/tmp/gcode_test_edit_unique"
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "f.txt")
    with open(p, "w") as f:
        f.write("hello world\n")
    out = edit_file.invoke({"path": p, "old_string": "world", "new_string": "there"})
    assert "Edited" in out
    with open(p) as f:
        assert f.read() == "hello there\n"


def test_edit_file_ambiguous():
    d = "/tmp/gcode_test_edit_ambiguous"
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "f.txt")
    with open(p, "w") as f:
        f.write("a a a\n")
    out = edit_file.invoke({"path": p, "old_string": "a", "new_string": "b"})
    assert "found 3 times" in out


def test_edit_file_not_found():
    out = edit_file.invoke({"path": "/no/such/file.txt", "old_string": "x", "new_string": "y"})
    assert "File not found" in out


def test_list_dir(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    out = list_dir.invoke({"path": str(tmp_path)})
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
