# Changelog

All notable changes to GCode are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Dedicated goodbye screen (ASCII logo, closing message, session ID) shown on exit via Ctrl+C/Ctrl+D, `/quit`, or interrupt
- `/status` slash command for a quick `git status` from inside a session

### Changed

### Fixed

### Removed

---

## [0.2.0] - 2026-08-06

### Added
- Slash command menu and interactive model picker in CLI
- Ollama local model support for offline coding assistance
- Pure-Python grep fallback for Windows compatibility (no system grep required)
- Comprehensive test coverage for grep functionality
- Interactive API key setup in CLI

### Changed
- Updated actions/checkout from v4 to v7
- Updated actions/setup-python from v5 to v7
- Updated langchain-core requirement to >=1.5.3
- Updated rich requirement to >=15.0.0
- Updated requests requirement to >=2.34.2
- Updated python-dotenv requirement to >=1.2.2

### Fixed
- Grep tool now works on all operating systems (Windows, Linux, macOS)

---

## [0.1.0] - 2026-07-16

### Added
- Initial public release
- Local, interactive AI coding CLI
- Stream answers and execute shell tools with confirmation

---

[Unreleased]: https://github.com/shauryagangrade/GCode/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/shauryagangrade/GCode/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/shauryagangrade/GCode/releases/tag/v0.1.0
