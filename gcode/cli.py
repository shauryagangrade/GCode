"""GCode command-line interface: argument parsing, REPL, and slash commands."""

import argparse
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage

from gcode import __version__
from gcode import tools as tool_module
from gcode.agent import build_model, run_turn, trim_history
from gcode.history import DEFAULT_SESSION, clear, load, save
from gcode.models import DEFAULT_MODEL, list_free_models, resolve_model_id
from gcode.ui import RichUI

SYSTEM_PROMPT = (
    "You are GCode, a coding agent that helps the user write, edit, and inspect "
    "code locally on this machine. Use the available tools to read and modify "
    "files, run shell commands (which require the user's approval), search the "
    "codebase, and work with git."
)


def _api_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", "")


def _print_help(ui: RichUI) -> None:
    ui.info(
        "GCode slash commands:\n"
        "  /help            Show this help\n"
        "  /models          List available free models\n"
        "  /model <id|#n>   Switch to a model (id, or #n index from /models)\n"
        "  /history         Show recent conversation turns\n"
        "  /clear           Start a fresh session (discard history)\n"
        "  /quit, /exit     Leave GCode\n"
        "Any other input is sent to the agent."
    )


def _cmd_models(ui: RichUI) -> None:
    ids, err = list_free_models()
    if err:
        ui.error(err)
        return
    if not ids:
        ui.info("No free models found.")
        return
    lines = ["Available free models (use '/model <id>' or '/model #n'):"]
    lines += [f"  {i:>2}. {mid}" for i, mid in enumerate(ids, 1)]
    ui.print("\n".join(lines), markup=False, highlight=False)


def _cmd_model(arg: str, api_key: str, state: dict, ui: RichUI) -> None:
    ids, _err = list_free_models()
    model_id, err = resolve_model_id(arg, ids)
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


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="gcode", description="GCode — a local, interactive AI coding CLI."
    )
    parser.add_argument("--model", help="Model ID (overrides GCODE_MODEL and default).")
    parser.add_argument("--session", default=DEFAULT_SESSION, help="Named session for history.")
    parser.add_argument("--yes", action="store_true", help="Auto-approve bash commands (unsafe).")
    parser.add_argument("--version", action="version", version=f"gcode {__version__}")
    args = parser.parse_args()

    api_key = _api_key()
    if not api_key:
        sys.exit(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your "
            "OpenRouter API key (https://openrouter.ai/keys)."
        )

    tool_module.set_auto_approve(args.yes)

    model_id = args.model or os.environ.get("GCODE_MODEL") or DEFAULT_MODEL
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
                ui.info("\nGoodbye.")
                break

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                parts = user_input[1:].split(None, 1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""
                if cmd in ("quit", "exit"):
                    ui.info("Goodbye.")
                    break
                elif cmd == "help":
                    _print_help(ui)
                elif cmd == "models":
                    _cmd_models(ui)
                elif cmd == "model":
                    _cmd_model(arg, api_key, state, ui)
                    model = state["model"]
                    model_id = state["model_id"]
                elif cmd == "history":
                    _cmd_history(messages, ui)
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
        ui.info("\nGoodbye.")

    save(session, messages)


if __name__ == "__main__":
    main()
