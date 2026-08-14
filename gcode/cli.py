"""GCode command-line interface: argument parsing, REPL, and slash commands."""

import argparse
import os
import sys

import questionary
from langchain_core.messages import SystemMessage

from gcode import __version__
from gcode import tools as tool_module
from gcode.agent import build_model, run_turn, trim_history
from gcode.history import DEFAULT_SESSION, clear, load, save
from gcode.models import (
    DEFAULT_MODEL,
    list_all_models,
    resolve_model_id,
)
from gcode.ollama import is_ollama_running, list_local_models, pull_model
from gcode.setup import get_api_key, load_env, setup_flow
from gcode.ui import RichUI

SYSTEM_PROMPT = (
    "You are GCode, a coding agent that helps the user write, edit, and inspect "
    "code locally on this machine. Use the available tools to read and modify "
    "files, run shell commands (which require the user's approval), search the "
    "codebase, and work with git."
)


def _print_help(ui: RichUI) -> None:
    ui.info(
        "[bold]GCode slash commands:[/bold]\n\n"
        "[bold cyan]General[/bold cyan]\n"
        "  /help            Show this help\n"
        "  /version         Show the installed GCode version\n"
        "  /quit, /exit     Leave GCode\n\n"
        "[bold cyan]Model[/bold cyan]\n"
        "  /models          List available models (OpenRouter + Ollama)\n"
        "  /model <id|#n>   Switch to a model (id, or #n index from /models)\n"
        "  /ollama          List/select local Ollama models\n"
        "  /pull <model>    Pull a model from Ollama registry\n\n"
        "[bold cyan]Session[/bold cyan]\n"
        "  /history         Show recent conversation turns\n"
        "  /clear           Start a fresh session (discard history)\n"
        "  /setup           Reconfigure API key\n\n"
        "[bold cyan]Git[/bold cyan]\n"
        "  /status          Show quick git status\n"
        "  /diff            Show staged and unstaged git changes\n\n"
        "Any other input is sent to the agent."
    )


def _cmd_models(ui: RichUI) -> str:
    """Show available models (OpenRouter + Ollama) as an interactive menu.

    Returns the selected model id, or ``""`` if the user cancelled.
    """
    all_models = list_all_models()
    if not all_models:
        ui.info("No models found. Check your network or Ollama server.")
        return ""

    # Build choice labels and maintain a mapping from label to model id
    choices = []
    label_to_id = {}
    for m in all_models:
        source_tag = "[ollama]" if m["source"] == "ollama" else "[openrouter]"
        size_tag = f" ({m['size']})" if m.get("size") else ""
        label = f"{m['id']}  {source_tag}{size_tag}"
        choices.append(label)
        label_to_id[label] = m["id"]

    try:
        selected = questionary.select(
            "Select a model:",
            choices=choices,
            instruction="(↑↓ navigate, Enter select, Esc cancel)",
        ).ask()
    except KeyboardInterrupt:
        return ""

    if selected is None:
        return ""

    # Return the model id from the mapping
    return label_to_id.get(selected, selected.split()[0])


def _cmd_model(arg: str, api_key: str, state: dict, ui: RichUI) -> None:
    all_models = list_all_models()
    model_id, err = resolve_model_id(arg, all_models)
    if err:
        ui.error(err)
        return
    try:
        state["model"] = build_model(model_id, api_key)
        state["model_id"] = model_id
        ui.info(f"Switched to model: {model_id}")
    except Exception as exc:
        ui.error(f"could not build model: {exc}")


def _cmd_history(messages, ui: RichUI) -> None:
    lines = []
    for m in messages:
        kind = m.__class__.__name__
        if kind == "HumanMessage":
            prefix, content = "You", m.content
        elif kind == "AIMessage":
            prefix, content = "GCode", m.content
        else:
            continue
        content = (content or "").strip()
        if content:
            lines.append(f"{prefix}: {content[:200]}")
    if not lines:
        ui.print("(no conversation yet)", markup=False)
    else:
        ui.print("\n".join(lines), markup=False, highlight=False)


def _cmd_status(ui: RichUI) -> None:
    """Show the current repository's git status (short form)."""
    result = tool_module.git_status.invoke({})
    ui.print(result, markup=False, highlight=False)


def _cmd_diff(ui: RichUI) -> None:
    """Show the current repository's staged and unstaged changes."""
    ui.print(tool_module.git_diff.invoke({}), markup=False, highlight=False)


def _cmd_version(ui: RichUI) -> None:
    """Show the installed GCode version."""
    ui.info(f"GCode v{__version__}")


def _cmd_ollama(ui: RichUI) -> str:
    """Show local Ollama models as an interactive menu.

    Returns the selected model id (prefixed with ``ollama/``), or ``""`` if the
    user cancelled or no models are available.
    """
    if not is_ollama_running():
        ui.info("Ollama server not detected at localhost:11434.")
        ui.info("Install Ollama: https://ollama.ai")
        return ""

    models, err = list_local_models()
    if err:
        ui.error(err)
        return ""
    if not models:
        ui.info("No models found locally. Use /pull <model> to download one.")
        return ""

    choices = [f"{m['name']}  ({m['size']})" for m in models]

    try:
        selected = questionary.select(
            "Select an Ollama model:",
            choices=choices,
            instruction="(↑↓ navigate, Enter select, Esc cancel)",
        ).ask()
    except KeyboardInterrupt:
        return ""

    if selected is None:
        return ""

    model_name = selected.split()[0]
    return f"ollama/{model_name}"


def _cmd_pull(model_name: str, ui: RichUI) -> None:
    """Pull a model from the Ollama registry."""
    if not model_name.strip():
        ui.error("Usage: /pull <model_name>  (e.g. /pull llama3.2)")
        return
    if not is_ollama_running():
        ui.error("Ollama server not detected. Is Ollama running?")
        ui.info("Install Ollama: https://ollama.ai")
        return

    ui.info(f"Pulling {model_name}...")
    success, msg = pull_model(model_name.strip())
    if success:
        ui.info(f"✓ {msg}")
    else:
        ui.error(msg)


def main() -> None:

    parser = argparse.ArgumentParser(
        prog="gcode", description="GCode — a local, interactive AI coding CLI."
    )
    parser.add_argument("--model", help="Model ID (overrides GCODE_MODEL and default).")
    parser.add_argument("--session", default=DEFAULT_SESSION, help="Named session for history.")
    parser.add_argument("--yes", action="store_true", help="Auto-approve bash commands (unsafe).")
    parser.add_argument("--version", action="version", version=f"gcode {__version__}")
    args = parser.parse_args()

    # Load ~/.gcode/.env first (setup module's config location)
    load_env()

    # Determine the model id early — Ollama models don't need an API key
    model_id = args.model or os.environ.get("GCODE_MODEL") or DEFAULT_MODEL
    using_ollama = model_id.startswith("ollama/")

    api_key = get_api_key()
    if not api_key and not using_ollama:
        api_key = setup_flow(skip_for_ollama=True)
        if api_key is None:
            # User chose to use Ollama — switch to the /ollama menu
            using_ollama = True
            _ui = RichUI()
            selected_model = _cmd_ollama(_ui)
            if selected_model:
                model_id = selected_model
                api_key = "ollama"  # placeholder; Ollama ignores it
            else:
                sys.exit("No model selected. Exiting.")
        elif not api_key:
            sys.exit("No API key provided. Exiting.")
    elif not api_key:
        # Running an Ollama model without any key — that's fine
        api_key = "ollama"

    tool_module.set_auto_approve(args.yes)

    try:
        model = build_model(model_id, api_key)
    except Exception as exc:
        sys.exit(f"Failed to initialize model: {exc}")

    ui = RichUI()

    session = args.session
    messages = load(session)
    if messages is None:
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
    else:
        ui.info(f"Resumed session '{session}' — {len(messages)} messages.")

    state = {"model": model, "model_id": model_id}

    ui.banner(__version__, model_id, session, os.getcwd())
    ui.info("Type /help for commands. Ctrl-D or /quit to exit.\n")

    try:
        while True:
            trim_history(messages)

            try:
                user_input = ui.prompt()
            except (EOFError, KeyboardInterrupt):
                ui.goodbye(session)
                break

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                parts = user_input[1:].split(None, 1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""
                if cmd in ("quit", "exit"):
                    ui.goodbye(session)
                    break
                elif cmd == "help":
                    _print_help(ui)
                elif cmd == "version":
                    _cmd_version(ui)
                elif cmd == "models":
                    selected_model = _cmd_models(ui)
                    if selected_model:
                        _cmd_model(selected_model, api_key, state, ui)
                        model = state["model"]
                        model_id = state["model_id"]
                elif cmd == "model":
                    _cmd_model(arg, api_key, state, ui)
                    model = state["model"]
                    model_id = state["model_id"]
                elif cmd == "ollama":
                    selected_model = _cmd_ollama(ui)
                    if selected_model:
                        _cmd_model(selected_model, api_key, state, ui)
                        model = state["model"]
                        model_id = state["model_id"]
                elif cmd == "pull":
                    _cmd_pull(arg, ui)
                elif cmd == "history":
                    _cmd_history(messages, ui)
                elif cmd == "status":
                    _cmd_status(ui)
                elif cmd == "diff":
                    _cmd_diff(ui)
                elif cmd == "setup":
                    new_key = setup_flow(force=True)
                    if new_key:
                        api_key = new_key
                        try:
                            state["model"] = build_model(model_id, api_key)
                            ui.info(f"API key updated. Model: {model_id}")
                        except Exception as exc:
                            ui.error(f"could not build model: {exc}")
                    else:
                        ui.info("Setup cancelled.")
                elif cmd == "clear":
                    clear(session)
                    messages[:] = [SystemMessage(content=SYSTEM_PROMPT)]
                    ui.info("Started a fresh session.")
                else:
                    ui.info(f"Unknown command: /{cmd} (try /help)")
                continue

            run_turn(user_input, messages, model, ui)
            save(session, messages)
    except KeyboardInterrupt:
        ui.goodbye(session)

    save(session, messages)


if __name__ == "__main__":
    main()
