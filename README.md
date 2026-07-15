# GCode

A local, interactive AI coding CLI. Chat with a free LLM (via OpenRouter) that can
read/write/edit files, run shell commands (with your approval), search your
codebase, and work with git.

## Install

```bash
pip install -e .
```

## Setup

Copy `.env.example` to `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-...
```

Get one at https://openrouter.ai/keys. (`OPENAI_API_KEY` is also accepted as a
fallback.)

## Use

```bash
gcode                            # start a session in the current directory
gcode --session work             # named, resumable session
gcode --model qwen/qwen3-coder:free
gcode --yes                      # auto-approve bash (unsafe — know what you run)
```

Commands (start a line with `/`):

- `/help` — show commands
- `/models` — list every free model on OpenRouter
- `/model <id|#n>` — switch models (use an id, or `#n` from `/models`)
- `/history` — show recent turns
- `/clear` — start a fresh session
- `/quit` — exit

Chat history persists across runs in `~/.gcode/`.

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
