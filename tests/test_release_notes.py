import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from extract_release_notes import extract_section  # noqa: E402

CHANGELOG = """\
# Changelog

## [Unreleased]

### Added
- unreleased thing

## [0.2.0] - 2026-08-06

### Added
- second release thing

### Fixed
- a bugfix

---

## [0.1.0] - 2026-07-16

### Added
- first release thing

---

[Unreleased]: https://example.com/compare/v0.2.0...HEAD
[0.2.0]: https://example.com/compare/v0.1.0...v0.2.0
[0.1.0]: https://example.com/releases/tag/v0.1.0
"""


def test_extracts_middle_section_without_trailing_divider():
    section = extract_section(CHANGELOG, "0.2.0")
    assert section.startswith("### Added")
    assert "second release thing" in section
    assert "a bugfix" in section
    assert "---" not in section
    assert "0.1.0" not in section


def test_extracts_last_section_before_link_reference_footer():
    section = extract_section(CHANGELOG, "0.1.0")
    assert section == "### Added\n- first release thing"


def test_extracts_unreleased_section():
    section = extract_section(CHANGELOG, "Unreleased")
    assert section == "### Added\n- unreleased thing"


def test_missing_version_raises():
    with pytest.raises(ValueError, match=r"no '## \[9\.9\.9\]' section"):
        extract_section(CHANGELOG, "9.9.9")
