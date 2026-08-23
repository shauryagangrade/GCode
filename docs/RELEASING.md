# Releasing GCode

## Automated: tag a version

Pushing a tag matching `v*` (e.g. `v0.3.0`) runs
[`.github/workflows/release.yml`](../.github/workflows/release.yml), which:

1. Verifies the **pushed tag itself** matches `gcode.__version__` before
   anything else — a forgotten version bump fails the release fast instead of
   shipping (or even building) the wrong artifacts under the wrong name.
2. Builds the sdist + wheel (`uv run python -m build`).
3. Runs the same checks as CI's build job: verifies the package imports,
   the `gcode` CLI entry point works, and `importlib.metadata.version('gcode')`
   agrees with `gcode.__version__`.
4. Runs `pip-audit` — a known-vulnerable dependency fails the release.
5. Extracts that version's section from [`CHANGELOG.md`](../CHANGELOG.md)
   (via [`scripts/extract_release_notes.py`](../scripts/extract_release_notes.py))
   and creates a GitHub Release using it as the release notes, with the
   sdist + wheel attached.

The workflow does not publish to PyPI — that needs credentials that
intentionally don't exist in CI, the same reasoning `ci.yml`'s build job
already follows.

## Manual steps before tagging

1. Move the changes from `## [Unreleased]` into a new `## [X.Y.Z] - <date>`
   section in `CHANGELOG.md` (the release notes are pulled from exactly this
   section, so it must exist and be non-empty before tagging).
2. Bump the version in `pyproject.toml`, `gcode/__init__.py`, and `setup.py`.
3. Commit, push, and confirm CI is green on `main`.
4. Tag and push: `git tag v0.3.0 && git push origin v0.3.0`.
5. Watch the `Release` workflow run, then verify the GitHub Release and
   attached artifacts.
