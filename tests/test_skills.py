import subprocess
from pathlib import Path

import pytest
from gcode import skills


def _write(directory: Path, name: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


# -- discover_skills / description parsing ----------------------------------


def test_discover_finds_project_and_user_skills(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "user" / ".gcode" / "skills")
    monkeypatch.setattr(skills, "CLAUDE_SKILLS_DIR", tmp_path / "nonexistent-claude-dir")
    _write(skills.USER_SKILLS_DIR, "review.md", "# Code review\nBe thorough.")

    project_root = tmp_path / "project"
    _write(
        skills.project_skills_dir(str(project_root)), "release.md", "# Release checklist\nTag it."
    )

    found = skills.discover_skills(str(project_root))

    assert set(found) == {"review", "release"}
    assert found["review"].source == "user"
    assert found["review"].description == "Code review"
    assert found["release"].source == "project"


def test_project_skill_overrides_same_named_user_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "user" / ".gcode" / "skills")
    monkeypatch.setattr(skills, "CLAUDE_SKILLS_DIR", tmp_path / "nonexistent-claude-dir")
    _write(skills.USER_SKILLS_DIR, "style.md", "# User style\nUser version.")

    project_root = tmp_path / "project"
    project_path = _write(
        skills.project_skills_dir(str(project_root)),
        "style.md",
        "# Project style\nProject version.",
    )

    found = skills.discover_skills(str(project_root))

    assert len(found) == 1
    assert found["style"].source == "project"
    assert found["style"].path == project_path


def test_discover_with_no_skills_dirs_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "nonexistent-user-dir")
    monkeypatch.setattr(skills, "CLAUDE_SKILLS_DIR", tmp_path / "nonexistent-claude-dir")
    assert skills.discover_skills(str(tmp_path / "nonexistent-project")) == {}


def test_discover_finds_claude_style_skill_folders(tmp_path):
    skill_dir = tmp_path / "graphify"
    skill_path = _write(
        skill_dir,
        "SKILL.md",
        '---\nname: graphify\ndescription: "Builds knowledge graphs."\n---\n\n# /graphify\n',
    )

    found = skills._skill_entries(tmp_path)

    assert found == {"graphify": skill_path}
    assert skills._describe(skill_path) == "Builds knowledge graphs."


def test_describe_parses_frontmatter_description_quoted_and_plain(tmp_path):
    quoted = _write(
        tmp_path,
        "quoted.md",
        '---\nname: q\ndescription: "A quoted description."\n---\n\n# Heading ignored\n',
    )
    plain = _write(
        tmp_path,
        "plain.md",
        "---\nname: p\ndescription: A plain description.\n---\n\nBody.\n",
    )

    assert skills._describe(quoted) == "A quoted description."
    assert skills._describe(plain) == "A plain description."


def test_describe_without_description_field_falls_back_to_heading(tmp_path):
    path = _write(tmp_path, "s.md", "---\nname: s\n---\n\n# The heading wins\nBody.\n")

    assert skills._describe(path) == "The heading wins"


def test_claude_source_is_lowest_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "CLAUDE_SKILLS_DIR", tmp_path / "claude" / "skills")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "user" / ".gcode" / "skills")
    project_root = tmp_path / "project"

    _write(
        skills.CLAUDE_SKILLS_DIR / "style",
        "SKILL.md",
        "---\ndescription: Claude version.\n---\n",
    )
    user_skills = skills.USER_SKILLS_DIR
    _write(user_skills, "style.md", "# User version")
    project_skills = skills.project_skills_dir(str(project_root))
    _write(project_skills, "style.md", "# Project version")

    found = skills.discover_skills(str(project_root))
    assert found["style"].source == "project"
    assert found["style"].description == "Project version"

    # Project copy removed -> the user-level one surfaces.
    (project_skills / "style.md").unlink()
    found = skills.discover_skills(str(project_root))
    assert found["style"].source == "user"
    assert found["style"].description == "User version"

    # User copy removed too -> the claude folder is the last resort.
    (user_skills / "style.md").unlink()
    found = skills.discover_skills(str(project_root))
    assert found["style"].source == "claude"
    assert found["style"].description == "Claude version."


def test_discover_ignores_folders_without_skill_md(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "CLAUDE_SKILLS_DIR", tmp_path / "claude" / "skills")
    (skills.CLAUDE_SKILLS_DIR / "not-a-skill").mkdir(parents=True)
    _write(skills.CLAUDE_SKILLS_DIR / "not-a-skill", "README.md", "# Not a skill")

    assert skills.discover_skills(str(tmp_path / "project")) == {}


def test_flat_file_wins_over_same_named_skill_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "user" / ".gcode" / "skills")
    flat = _write(skills.USER_SKILLS_DIR, "duo.md", "# Flat version")
    _write(skills.USER_SKILLS_DIR / "duo", "SKILL.md", "---\ndescription: Folder version.\n---")

    found = skills.discover_skills(str(tmp_path / "project"))

    assert found["duo"].path == flat
    assert found["duo"].description == "Flat version"


def test_describe_falls_back_to_plain_first_line(tmp_path):
    path = _write(tmp_path, "plain.md", "Just a plain first line.\nMore text.")
    assert skills._describe(path) == "Just a plain first line."


def test_describe_empty_file_reports_no_description(tmp_path):
    path = _write(tmp_path, "empty.md", "")
    assert skills._describe(path) == "(no description)"


def test_skill_read_returns_full_content(tmp_path):
    path = _write(tmp_path, "s.md", "# Title\nBody line.")
    skill = skills.Skill(name="s", description="Title", source="project", path=path)
    assert skill.read() == "# Title\nBody line."


# -- import_skill --------------------------------------------------------------


def test_import_skill_rejects_flag_shaped_package(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: "/usr/bin/npx")
    with pytest.raises(RuntimeError, match="invalid package name"):
        skills.import_skill("--some-flag", str(tmp_path))


def test_import_skill_raises_when_npx_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: None)
    with pytest.raises(RuntimeError, match="npx not found"):
        skills.import_skill("some-pkg", str(tmp_path))


def test_import_skill_raises_on_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="failed \\(exit 1\\): boom"):
        skills.import_skill("some-pkg", str(tmp_path))


def test_import_skill_raises_when_no_markdown_produced(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="did not write any .md skill files"):
        skills.import_skill("some-pkg", str(tmp_path))


def test_import_skill_raises_on_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        skills.import_skill("some-pkg", str(tmp_path), timeout=5)


def test_import_skill_copies_produced_markdown_into_project_skills_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        # Simulate the package writing a skill file into its scratch cwd.
        (Path(cwd) / "imported-skill.md").write_text("# Imported\nFrom npx.", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    project_root = tmp_path / "project"
    imported = skills.import_skill("some-pkg", str(project_root))

    assert imported == ["imported-skill"]
    dest = skills.project_skills_dir(str(project_root)) / "imported-skill.md"
    assert dest.read_text(encoding="utf-8") == "# Imported\nFrom npx."


def test_import_skill_refuses_to_overwrite_existing_skill_file(tmp_path, monkeypatch):
    monkeypatch.setattr(skills.shutil, "which", lambda cmd: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        (Path(cwd) / "imported-skill.md").write_text("# New version", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    project_root = tmp_path / "project"
    dest = skills.project_skills_dir(str(project_root)) / "imported-skill.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("# Hand-written original", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to overwrite existing skill file"):
        skills.import_skill("some-pkg", str(project_root))

    assert dest.read_text(encoding="utf-8") == "# Hand-written original"
