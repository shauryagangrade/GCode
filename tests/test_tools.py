import os

from gcode.tools import edit_file, grep, list_dir


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
    out = edit_file.invoke(
        {"path": "/no/such/file.txt", "old_string": "x", "new_string": "y"}
    )
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
