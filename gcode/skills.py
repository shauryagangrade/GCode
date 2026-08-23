"""Importable "skills": reusable instructions that extend the agent.

A skill is a single Markdown file describing extra behavior for GCode to
follow (a domain checklist, house style, project-specific conventions). It
lives in a dedicated ``skills/`` folder under ``.gcode/``, at either the
project level (``<project_root>/.gcode/skills/``) or the user level
(``~/.gcode/skills/``) - a project skill overrides a user skill of the same
name, the same precedence ``.gcoderc`` config already uses.

Claude Code-style skills are also discovered natively: ``~/.claude/skills``
is scanned as an additional (lowest-precedence) source, and both layouts are
accepted - a flat ``<name>.md`` file or a ``<name>/SKILL.md`` file inside a
folder, with a YAML frontmatter ``description:`` preferred for listings.

Skills can also be imported from an npm package via ``npx``: running
``npx <package>`` in a scratch directory and copying any Markdown files it
writes there into the project's skills folder treats that package as the
skill's source, without GCode needing its own package registry or format.
"""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

SKILLS_DIRNAME = "skills"
USER_SKILLS_DIR = Path.home() / ".gcode" / SKILLS_DIRNAME
CLAUDE_SKILLS_DIR = Path.home() / ".claude" / SKILLS_DIRNAME
NPX_TIMEOUT = 120


@dataclass
class Skill:
    name: str
    description: str
    source: str  # "project", "user", or "claude"
    path: Path

    def read(self) -> str:
        """Return the skill file's full Markdown content."""
        return self.path.read_text(encoding="utf-8")


def project_skills_dir(project_root: str) -> Path:
    """Return the project-level skills folder for ``project_root``."""
    return Path(project_root) / ".gcode" / SKILLS_DIRNAME


def _frontmatter_field(lines: list[str], field: str) -> str | None:
    """Return a top-level ``field:`` value from YAML frontmatter, if present.

    ``lines[0]`` must be the opening ``---`` fence; the fence's closing line
    ends the frontmatter block. Only single-line values are handled - good
    enough for SKILL.md descriptions, and no PyYAML dependency needed.
    """
    if not lines or lines[0].strip() != "---":
        return None
    prefix = field.lower() + ":"
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return None
        if stripped.lower().startswith(prefix):
            value = stripped[len(prefix) :].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            return value or None
    return None


def _describe(path: Path) -> str:
    """Describe ``path``: its frontmatter description, else first non-blank
    line with any leading '#' stripped."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "(no description)"
    description = _frontmatter_field(lines, "description")
    if description:
        return description

    body = lines
    if lines and lines[0].strip() == "---":
        closes = [i for i in range(1, len(lines)) if lines[i].strip() == "---"]
        body = lines[closes[0] + 1 :] if closes else lines[1:]
    for line in body:
        line = line.strip()
        if line:
            return line.lstrip("#").strip() or "(no description)"
    return "(no description)"


def _skill_entries(directory: Path) -> dict[str, Path]:
    """Return every skill Markdown file in ``directory``, keyed by name.

    Both layouts are accepted: a flat ``<name>.md`` file (GCode-native) and
    a Claude Code-style ``<name>/SKILL.md`` folder. A flat file wins over a
    same-named folder; folders without a ``SKILL.md`` are ignored.
    """
    entries: dict[str, Path] = {}
    for path in sorted(directory.glob("*/SKILL.md")):
        if path.is_file():
            entries[path.parent.name] = path
    for path in sorted(directory.glob("*.md")):
        if path.is_file():
            entries[path.stem] = path
    return entries


def discover_skills(project_root: str) -> dict[str, Skill]:
    """Return every skill visible from ``project_root``, keyed by name.

    Scans the Claude Code folder, then the user-level folder, then the
    project-level folder; a skill with the same name replaces one from a
    lower-precedence source (project beats user beats claude).
    """
    skills: dict[str, Skill] = {}
    sources = (
        ("claude", CLAUDE_SKILLS_DIR),
        ("user", USER_SKILLS_DIR),
        ("project", project_skills_dir(project_root)),
    )
    for source, directory in sources:
        if not directory.is_dir():
            continue
        for name, path in sorted(_skill_entries(directory).items()):
            skills[name] = Skill(name=name, description=_describe(path), source=source, path=path)
    return skills


def import_skill(package: str, project_root: str, timeout: int = NPX_TIMEOUT) -> list[str]:
    """Fetch a skill via ``npx <package>`` into the project's skills folder.

    Runs the package with ``npx --yes`` in a scratch directory; whatever
    Markdown files it writes there are copied into
    ``project_skills_dir(project_root)`` and treated as the skill(s) it
    provides. Returns the imported skill names (their filename stems).

    Raises RuntimeError if ``package`` is flag-shaped rather than a package
    name, ``npx`` isn't installed, the command fails or times out, it writes
    no Markdown files, or a produced file would overwrite an existing skill.
    """
    if package.startswith("-"):
        raise RuntimeError(f"invalid package name: {package} (must not start with '-')")

    npx_path = shutil.which("npx")
    if npx_path is None:
        raise RuntimeError("npx not found - install Node.js to import skills via npx")

    with tempfile.TemporaryDirectory(prefix="gcode-skill-") as scratch:
        try:
            result = subprocess.run(  # nosec B603 - no shell; import is user-approved before this runs
                [npx_path, "--yes", package],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"npx {package} timed out after {timeout}s") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"npx {package} failed (exit {result.returncode}): {detail}")

        produced = sorted(Path(scratch).glob("*.md"))
        if not produced:
            raise RuntimeError(f"npx {package} did not write any .md skill files")

        target_dir = project_skills_dir(project_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        conflicts = [path.name for path in produced if (target_dir / path.name).exists()]
        if conflicts:
            raise RuntimeError(
                "refusing to overwrite existing skill file(s): "
                + ", ".join(conflicts)
                + " - delete or rename them first"
            )
        imported = []
        for path in produced:
            shutil.copyfile(path, target_dir / path.name)
            imported.append(path.stem)
        return imported
