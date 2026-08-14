# GCode

![Build](https://github.com/shauryagangrade/GCode/actions/workflows/ci.yml/badge.svg)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/gcode.svg)](https://pypi.org/project/gcode/)
[![Stars](https://img.shields.io/github/stars/shauryagangrade/GCode?style=social)](https://github.com/shauryagangrade/GCode)

A local, interactive AI coding CLI. Chat with a free LLM (via OpenRouter) that can
read/write/edit files, run shell commands (with your approval), search your
codebase, and work with git.

![GCode demo](docs/demo.gif)

## Contributing

GCode is community-built, and contributions of every kind are welcome — bug
reports, docs, tests, and features.

- **First-time contributor?** Start with a
  [good first issue](https://github.com/shauryagangrade/GCode/labels/good%20first%20issue).
- Need more context? Browse the
  [help wanted](https://github.com/shauryagangrade/GCode/labels/help%20wanted) issues.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Install

```bash
pip install -e .
```

## Setup

GCode reads your API key from `~/.gcode/.env` (not a project-root `.env`).
Create it from the template and add your OpenRouter API key:

```bash
mkdir -p ~/.gcode
cp .env.example ~/.gcode/.env
```

Then edit `~/.gcode/.env`:

```
OPENROUTER_API_KEY=sk-or-...
```

Get one at https://openrouter.ai/keys. (`OPENAI_API_KEY` is also accepted as a
fallback.)

## Configuration file

GCode reads optional settings from a `.gcoderc` file (in the project root, or
`~/.gcode/.gcoderc` for user-wide defaults). The format is simple `key = value`
lines with `#` comments. Command-line flags and environment variables still
take precedence over the file.

```
# .gcoderc
model = qwen/qwen3-coder:free
auto_approve = false
bash_timeout = 300
system_prompt = You are GCode, a coding agent.
```

Supported keys:

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `model` | string | first free model | Default model id (overridden by `--model` / `GCODE_MODEL`) |
| `auto_approve` | bool | `false` | Skip bash confirmation (overridden by `--yes`) |
| `bash_timeout` | int | `300` | Seconds before a bash command is killed |
| `system_prompt` | string | built-in | Custom system prompt for new sessions |

## Use

```bash
gcode                            # start a session in the current directory
gcode --session work             # named, resumable session
gcode --model qwen/qwen3-coder:free
gcode --yes                      # auto-approve bash (unsafe — know what you run)
```

Commands (start a line with `/`):

- `/help` — show commands
- `/version` — show the installed GCode version
- `/models` — list every free model on OpenRouter
- `/model <id|#n>` — switch models (use an id, or `#n` from `/models`)
- `/history` — show recent turns
- `/status` — quick git status
- `/clear` — start a fresh session
- `/quit` — exit

Chat history persists across runs in `~/.gcode/`.

## Demo GIF

`docs/demo.gif` is recorded from a real session with [vhs](https://github.com/charmbracelet/vhs):

```bash
brew install vhs          # or: go install github.com/charmbracelet/vhs@latest
vhs demo/demo.tape        # writes docs/demo.gif
```

Notes for editing `demo/demo.tape`:

- `Set TypingSpeed` needs explicit units — `155ms`, not `155` (vhs parses a bare
  number as `155s` = 155 seconds per keystroke).
- Typed `/commands` can't be scripted: GCode opens an interactive slash menu on
  `/`, which swallows the rest of the line. Launch with `--model <id>` instead
  of `/model` to switch models in the recording.
- Use `--yes` so `execute_bash` runs without the `y/n` gate (no keystroke
  timing to sync), and pick a tool-capable free model that responds reliably.
- The recording runs in real time, so give each turn generous `Sleep` windows —
  free models are slow and rate-limited.

GCode streams the assistant's replies token-by-token, renders Markdown, and shows
each tool call as `⏺ Tool(args)` with a `y/n` gate before bash runs (skip the gate
with `--yes`).

## Models

The default `qwen/qwen3-coder:free` supports tool use. Not every free model
does — some (e.g. `meta-llama/llama-3.2-3b-instruct:free`) return a 404
"No endpoints found that support tool use". Stick to tool-capable models, or
any model you pass via `/model` / `--model` / `GCODE_MODEL`. Free models are
also heavily rate-limited on OpenRouter's shared tier; if you get a `429`,
wait a moment and retry, or use your own OpenRouter key for higher limits.

## Safety

Bash commands require a `y/n` confirmation by default. Only use `--yes` if you
trust the agent and your prompts — it will run whatever the model requests.

## Contributors

Thanks to everyone who has contributed to GCode, whether through code, documentation, bug reports, testing, or other contributions. ❤️

Your contributions help make GCode better for everyone.

<a href="https://github.com/shauryagangrade/GCode/graphs/contributors"> <img src="https://contrib.rocks/image?repo=shauryagangrade/GCode" /> </a>

Contributions are always welcome! See CONTRIBUTING.md to get started.
