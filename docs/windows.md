# Windows setup and troubleshooting

GCode is a Python CLI that shells out to local tools, so the experience on
Windows depends on which environment you run it in. This guide covers the
three common options — native Windows, WSL2, and Git Bash — and documents
what is known to work and what is not yet supported.

## Choose an environment

| Environment | Best for | Tool support |
| --- | --- | --- |
| [WSL2](#wsl2-recommended) (recommended) | Full experience: bash, git, grep | `execute_bash`, git tools, grep all work as on Linux |
| [Native Windows](#native-windows) | Quick tries, Python-only workflows | `execute_bash` uses `cmd.exe` (bash syntax fails), git tools need Git for Windows, grep falls back to pure Python |
| [Git Bash](#git-bash) | Users already on Git Bash | Mostly works, but see the [limitations](#known-limitations) below |

## Requirements

- Python 3.10 or newer on `PATH`
- An [OpenRouter API key](https://openrouter.ai/keys) (`OPENAI_API_KEY` is
  also accepted as a fallback)
- `git` on `PATH` for the git tools (`/status`, `/diff`, `git_commit`)

## WSL2 (recommended)

WSL2 gives you a real Linux environment where GCode's bash tool and git tools
behave exactly as documented.

1. Install WSL2 and a distro (e.g. Ubuntu):
   ```powershell
   wsl --install
   ```
   Reboot when prompted, then open the Ubuntu terminal.
2. Inside WSL, install Python 3.10+ and git:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
   ```
3. Clone and install GCode:
   ```bash
   git clone https://github.com/shauryagangrade/GCode.git
   cd GCode
   python3 -m pip install -e .
   ```
4. Create the env file inside WSL and add your API key:
   ```bash
   mkdir -p ~/.gcode
   cp .env.example ~/.gcode/.env
   ```
5. Run it:
   ```bash
   gcode
   ```

Your `~/.gcode` directory lives inside the WSL filesystem. To use the same
API key from Windows and WSL you can copy `%USERPROFILE%\.gcode\.env` into
WSL (`cp /mnt/c/Users/<you>/.gcode/.env ~/.gcode/.env`), but keeping them
separate is simpler.

## Native Windows

GCode runs as a normal Python program on Windows. The CLI, `/models` menu,
history, and the pure-Python `grep` fallback work; the `execute_bash` tool
has real limitations (see below).

1. Install Python 3.10+ from [python.org](https://python.org) (check
   "Add python.exe to PATH" during install).
2. Open a terminal (PowerShell or cmd) and install:
   ```powershell
   pip install -e .
   ```
   (Or `pip install -e .` from the GCode checkout if you cloned it first.)
3. Create the env file. On Windows, `~` is your user profile directory:
   ```powershell
   mkdir $env:USERPROFILE\.gcode
   Copy-Item .env.example $env:USERPROFILE\.gcode\.env
   ```
   That places it at `C:\Users\<you>\.gcode\.env`.
4. Edit it with your key and run `gcode`.

### Known limitation: `execute_bash` uses cmd.exe

`execute_bash` runs commands through Python's `shell=True`. On native
Windows that invokes `cmd.exe`, **not** bash, so bash syntax fails:

- `grep` pipelines, `&&`-chains of POSIX commands, `export FOO=bar`,
  `$HOME` references, and single-quote quoting do not behave as on Linux.
- Tools like `curl` may not exist on stock Windows (`curl.exe` is present on
  modern builds, but the classic `curl` alias may route to PowerShell).

This is tracked in [issue #54](https://github.com/shauryagangrade/GCode/issues/54)
(execute_bash and git tools assume POSIX/bash — broken on native Windows).
Until it is fixed, prefer WSL2 or Git Bash for anything that shells out.

### Known limitation: git tools need Git for Windows

The git tools (`/status`, `/diff`, `git_commit`) call the `git` binary. On
native Windows you must install [Git for Windows](https://git-scm.com) and
make sure `git` is on `PATH` (the installer offers this). Git Bash is
included with Git for Windows, so installing it covers both cases.

## Git Bash

Git Bash (installed with Git for Windows) provides a POSIX-ish shell with
`bash`, `git`, and `grep` on `PATH`. GCode's `execute_bash` will find
`bash` via `shell=True`, so most commands behave as on Linux.

- Run `gcode` from a Git Bash window, and `execute_bash` commands are
  interpreted by bash.
- The pure-Python `grep` fallback is not used because the MSYS `grep` is on
  `PATH`; keep `--include` globs attached to the flag (the tool does this
  automatically) so MSYS does not glob-expand them.
- Paths passed to tools should use the MSYS/Git Bash view (`/c/Users/<you>/...`
  or `C:/Users/<you>/...`), not `cmd`-style paths.

## Env-file paths

GCode reads its API key from `~/.gcode/.env` (not a project-root `.env`):

| Environment | Location |
| --- | --- |
| WSL2 / Linux | `~/.gcode/.env` → `/home/<you>/.gcode/.env` |
| Native Windows | `~/.gcode/.env` → `C:\Users\<you>\.gcode\.env` |
| Git Bash | `~/.gcode/.env` → `C:\Users\<you>\.gcode\.env` (same as Windows) |

Optional user-wide settings live in `~/.gcode/.gcoderc` (see the README
[Configuration file](../README.md#configuration-file) section); a
project-local `.gcoderc` in the directory you launch GCode from overrides it.

Session history also persists under `~/.gcode/`.

## Known limitations summary

- `execute_bash` on native Windows uses `cmd.exe`, not bash — bash-only
  syntax fails ([#54](https://github.com/shauryagangrade/GCode/issues/54)).
- Git tools require a `git` binary on `PATH` (Git for Windows / WSL).
- The `grep` tool prefers a system `grep` when available and falls back to a
  pure-Python search otherwise, so it works everywhere, but performance on
  very large trees is better with the system binary.
- Free OpenRouter models are heavily rate-limited on the shared tier; a
  `429` response means "wait and retry" (see README Models section).

## Getting help

- Open an issue with the [bug report template](../.github/ISSUE_TEMPLATE/bug_report.yml)
  and include your environment (native Windows / WSL2 / Git Bash, Python
  version, `gcode --version` output).
- If bash-style commands fail, note the exact command and whether you ran
  from PowerShell, cmd, or Git Bash — that tells us which shell the tool
  actually used.
