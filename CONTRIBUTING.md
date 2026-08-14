# Contributing to GCode

Thanks for contributing! GCode is community-built, and bug reports, docs,
tests, and features are all welcome.

- **First-time contributor?** Start with a
  [good first issue](https://github.com/shauryagangrade/GCode/labels/good%20first%20issue).
- Looking for more? Browse the
  [help wanted](https://github.com/shauryagangrade/GCode/labels/help%20wanted) issues.
- Open an issue before starting large work so maintainers can steer scope.

---

## Quick Setup

GCode uses [uv](https://docs.astral.sh/uv/) for dependency management and
development. Install uv first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone and set up:

```bash
git clone https://github.com/shauryagangrade/GCode.git
cd GCode
uv sync --extra dev
mkdir -p ~/.gcode && cp .env.example ~/.gcode/.env
```

Fill in your `OPENROUTER_API_KEY` in `~/.gcode/.env` (see
[README setup](README.md#setup)), then run:

```bash
uv run gcode
```

> **Windows?** See [docs/windows.md](docs/windows.md) for native, WSL2, and
> Git Bash instructions and known limitations.

---

## Local checks

CI runs these exact commands (see `.github/workflows/ci.yml`). Run them all
locally before pushing:

```bash
uv run ruff check .                 # lint
uv run ruff format --check .        # formatting
uv run mypy gcode                   # type check
uv run bandit -q -r gcode/ -c pyproject.toml   # security scan
uv run python -m compileall -q gcode demo      # compile check
uv run pytest                       # test suite
```

The test suite runs against Python 3.10–3.13 in CI, so the same code should
pass on any of those versions locally.

---

## How to Contribute

### Reporting Bugs

Open an issue using the
[bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Include steps
to reproduce, expected vs actual behavior, and environment info.

### Requesting Features

Open an issue using the
[feature request template](.github/ISSUE_TEMPLATE/feature_request.yml).

### Submitting a PR

1. Fork the repo and create a branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Run the [local checks](#local-checks) — all must pass
4. Open a PR against `main` and describe *why*, not just *what*

---

## Adding a new tool or slash command

GCode exposes two kinds of commands:

- **Agent tools** — what the model can call (read/write files, run bash,
  git operations).
- **Slash commands** — what the *user* types in the REPL (`/help`, `/models`,
  `/status`, ...).

### Adding an agent tool

Tools live in `gcode/tools.py`. Each is a function decorated with
`@tool` from `langchain.tools`, so the model receives a clean schema and
description.

1. Write the function in `gcode/tools.py` with a docstring that describes
   when to use it and its arguments (the docstring becomes the tool schema).
2. Add it to the `ALL_TOOLS` list (which also sets the order tools are
   offered to the model).
3. Add it to `TOOL_MAP` — the `name -> tool` dict used to dispatch model
   calls: `TOOL_MAP = {t.name: t for t in ALL_TOOLS}`.
4. Add a unit test in `tests/` (see `tests/test_tools.py` for the pattern).
5. Run `uv run pytest` and the lint checks above.

### Adding a slash command

Slash commands are handled in `gcode/cli.py` inside the `main()` REPL loop.
The interactive menu is driven by `_SLASH_COMMANDS` in `gcode/ui.py`, and
`/help` text lives in `_print_help` in `gcode/cli.py`.

1. Add the command handler in `gcode/cli.py` — a `_cmd_*` function plus a
   `elif cmd == "..."` branch in `main()`.
2. Add the command to `_SLASH_COMMANDS` in `gcode/ui.py` as a
   `("/command", "one-line description")` tuple so it appears in the
   interactive `/` menu.
3. Add it to `_print_help` in `gcode/cli.py` under the right group
   (General / Model / Session / Git).
4. Update the README's [Commands](README.md#use) list.
5. Add a unit test where the command has testable behavior (see
   `tests/test_cli.py`); commands that only render UI may be covered by
   `tests/test_ui.py`.
6. Run `uv run pytest` and the lint checks above.

---

## Code Style

- Follow the lint rules enforced by `ruff` (targets Python 3.10+, line
  length 100).
- Write clean, readable code with descriptive variable names.
- Add type annotations — `mypy gcode` must stay green.
- Keep changes narrow: one PR per change.

---

## PR Guidelines

- One PR per change — keep scope tight
- PR description must explain *why*, not just *what*
- Ensure any new tools or CLI commands are documented (this checklist above)
- AI-assisted code is welcome — provided you have reviewed and tested the output

---

## Commit Style

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add dark mode toggle
fix: correct timezone offset in tournament dates
docs: update quick start steps
```

Types: `feat | fix | docs | style | refactor | perf | test | ci | chore`

---

## Community

GitHub Issues: https://github.com/shauryagangrade/GCode/issues
