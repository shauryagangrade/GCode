"""Importable "skills": reusable instructions that extend the agent.

A skill is a single Markdown file describing extra behavior for GCode to
follow (a domain checklist, house style, project-specific conventions). It
lives in a dedicated ``skills/`` folder under ``.gcode/``, at either the
project level (``<project_root>/.gcode/skills/``) or the user level
(``~/.gcode/skills/``) - a project skill overrides a user skill of the same
name, the same precedence ``.gcoderc`` config already uses.

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
NPX_TIMEOUT = 120


@dataclass
class Skill:
    name: str
    description: str
    source: str  # "project" or "user"
    path: Path

    def read(self) -> str:
        """Return the skill file's full Markdown content."""
        return self.path.read_text(encoding="utf-8")


def project_skills_dir(project_root: str) -> Path:
    """Return the project-level skills folder for ``project_root``."""
    return Path(project_root) / ".gcode" / SKILLS_DIRNAME


def _describe(path: Path) -> str:
    """First non-blank line of ``path``, with any leading '#' stripped."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                return line.lstrip("#").strip() or "(no description)"
    except OSError:
        pass
    return "(no description)"


def discover_skills(project_root: str) -> dict[str, Skill]:
    """Return every skill visible from ``project_root``, keyed by name.

    Scans the user-level folder, then the project-level folder; a project
    skill with the same name replaces the user one.
    """
    skills: dict[str, Skill] = {}
    sources = (("user", USER_SKILLS_DIR), ("project", project_skills_dir(project_root)))
    for source, directory in sources:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            name = path.stem
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
