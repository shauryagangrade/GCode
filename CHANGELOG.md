# Changelog

All notable changes to GCode are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Dedicated goodbye screen (ASCII logo, closing message, session ID) shown on exit via Ctrl+C/Ctrl+D, `/quit`, or interrupt
- `/status` slash command for a quick `git status` from inside a session
- `/version` slash command to show the installed GCode version from inside a session
- `/diff` slash command to show staged and unstaged git changes
- Case-insensitive `grep` via the `ignore_case` tool parameter
- `/models` now shows each model's context window and tool support
- Optional `.gcoderc` configuration file (`~/.gcode/.gcoderc` or project root) to set model, auto-approve, bash timeout, and system prompt
- `--cwd DIR` flag to run GCode against another project (like `git -C`)
- Unit tests for history persistence, API-key setup, and grep differential behavior against a real `grep`

### Changed
- `/help` command listing grouped by category (General, Model, Session, Git) so the growing command set stays scannable
- Setup docs (README, CONTRIBUTING) now point at `~/.gcode/.env` — the location the app actually reads — instead of a project-root `.env`

### Fixed
- `execute_bash` no longer hangs or crashes when its approval prompt runs in a non-interactive environment (CI, Docker, pipes); it now rejects the command, and `--yes` can be used to auto-approve
- Session history saves are atomic (temp file + rename) and failures are reported instead of silently swallowed; a corrupt session file now warns and names the path instead of masquerading as an empty conversation
- `grep` keeps the glob attached to `--include=<glob>` so Git-for-Windows' MSYS runtime cannot expand it against the wrong directory
- Single-file `grep` output is now consistent between the system binary and the Python fallback (`-H` always emits the filename prefix)
- Auto-approve is read at call time so toggling it mid-session takes effect immediately
- Common errors now include actionable next-step hints (missing API key, network failures, unknown model IDs)
- Rich markup in tool results and error messages is escaped so it renders as plain text
- Python `grep` fallback skips binary and unreadable files, and invalid regexes get clearer guidance

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
