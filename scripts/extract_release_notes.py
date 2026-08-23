"""Extract one version's section from CHANGELOG.md for a GitHub Release body.

CHANGELOG.md follows Keep a Changelog: each release is a `## [X.Y.Z] - date`
heading followed by `### Added/Changed/Fixed/Removed` subsections, ending at
the next `## [` heading (or end of file). This pulls just that section so the
release workflow can use it as the release's notes instead of hand-writing
them a second time.
"""

import argparse
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^## \[(?P<version>[^\]]+)\]")
# The file ends with a block of `[label]: url` reference-link definitions
# (one per released version) rather than another `## [` heading, so that
# block needs its own terminator to keep it out of the last section.
LINK_REF_RE = re.compile(r"^\[[^\]]+\]:\s")


def extract_section(changelog_text: str, version: str) -> str:
    """Return the body of the `## [version]` section, without its heading.

    Raises ValueError if no section for `version` exists.
    """
    lines = changelog_text.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if start is not None and LINK_REF_RE.match(line):
            end = i
            break
        match = HEADING_RE.match(line)
        if match is None:
            continue
        if start is not None:
            end = i
            break
        if match.group("version") == version:
            start = i + 1

    if start is None:
        raise ValueError(f"no '## [{version}]' section found in CHANGELOG.md")

    section_lines = lines[start:end]
    # Drop the trailing "---" divider (and any blank lines around it) that
    # separates one release's section from the next in this file.
    while section_lines and section_lines[-1].strip() in ("", "---"):
        section_lines.pop()

    section = "\n".join(section_lines).strip("\n")
    if not section:
        raise ValueError(f"'## [{version}]' section in CHANGELOG.md is empty")
    return section


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="release version, without a leading 'v' (e.g. 0.3.0)")
    parser.add_argument(
        "--changelog",
        default=Path(__file__).resolve().parent.parent / "CHANGELOG.md",
        type=Path,
        help="path to CHANGELOG.md (default: repo root)",
    )
    args = parser.parse_args(argv)

    try:
        text = args.changelog.read_text(encoding="utf-8")
        print(extract_section(text, args.version))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
