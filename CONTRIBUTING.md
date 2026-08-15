# Contributing to GCode

---

## Quick Setup

```bash
git clone https://github.com/shauryagangrade/GCode.git
cd GCode
pip install -e .
mkdir -p ~/.gcode && cp .env.example ~/.gcode/.env
gcode
```

You will need an OpenRouter API key. Copy the `.env.example` file to
`~/.gcode/.env` and fill in your `OPENROUTER_API_KEY`.

---

## How to Contribute

### Reporting Bugs
Open an issue using the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include steps to reproduce, expected vs actual behavior, and environment info.

### Requesting Features
Open an issue using the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).

### Submitting a PR

1. Fork the repo and create a branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Verify: `pytest` — must pass clean
4. Open a PR against `main`

---

## Good First Issues

Look for issues labeled
[`good first issue`](https://github.com/shauryagangrade/GCode/labels/good%20first%20issue)
or [`help wanted`](https://github.com/shauryagangrade/GCode/labels/help%20wanted) —
both are reserved for contributors submitting their first PR to GCode. If
you've already had a PR merged, a bot will unassign you and close any PR that
claims them, so pick an unreserved issue instead.

---

## Code Style

- Follow PEP 8 styling guidelines.
- Write clean, readable code with descriptive variable names.
- Ensure all tests pass before opening a PR.

---

## PR Guidelines

- One PR per change — keep scope tight
- PR description must explain *why*, not just *what*
- Ensure any new tools or CLI commands are documented.
- AI-assisted code is welcome — provided you have reviewed and tested the output.

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
