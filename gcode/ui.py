"""Rich-based terminal UI for GCode, mimicking the Claude Code look.

A single ``RichUI`` wraps a ``rich.console.Console`` and exposes hooks the agent
loop calls: streaming assistant text (spinner -> live Markdown), tool-call
display, a permission gate, and status/error output.
"""

import questionary
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text

_TRUNCATE_STEP = 80  # re-render Markdown only after this many new characters

# Slash commands available in the interactive menu
_SLASH_COMMANDS = [
    ("/help", "Show available commands"),
    ("/version", "Show the installed GCode version"),
    ("/models", "List available models (OpenRouter + Ollama)"),
    ("/model", "Switch to a different model"),
    ("/ollama", "List/select local Ollama models"),
    ("/pull", "Pull a model from Ollama registry"),
    ("/setup", "Reconfigure API key"),
    ("/history", "Show recent conversation turns"),
    ("/status", "Show quick git status"),
    ("/diff", "Show staged and unstaged git changes"),
    ("/clear", "Start a fresh session (discard history)"),
    ("/quit", "Leave GCode"),
]

_GCODE_LOGO = r"""
 ██████╗  ██████╗ ██████╗ ██████╗ ███████╗
██╔════╝ ██╔════╝██╔═══██╗██╔══██╗██╔════╝
██║  ███╗██║     ██║   ██║██║  ██║█████╗
██║   ██║██║     ██║   ██║██║  ██║██╔══╝
╚██████╔╝╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═════╝  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
""".strip("\n")


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _summarize_tool(name: str, args: dict) -> str:
    """One-line preview of a tool call's arguments for display."""
    if name == "execute_bash":
        return _truncate(args.get("command", ""), 200)
    if "path" in args:
        path = args.get("path", "")
        if not isinstance(path, str):
            path = ""
        return _truncate(path, 120)
    items = ", ".join(f"{k}={_truncate(v, 60)}" for k, v in args.items())
    return _truncate(items, 160)


class RichUI:
    def __init__(self):
        self.console = Console()
        self._live = None
        self._buffer = ""
        self._last_len = 0

    # -- banner / prompt ---------------------------------------------------
    def banner(self, version: str, model: str, session: str, cwd: str) -> None:
        self.console.print(
            Rule(
                f"[bold cyan]GCode[/] [dim]v{version}[/]   "
                f"[dim]model:[/] {model}   [dim]cwd:[/] {cwd}   "
                f"[dim]session:[/] {session}"
            )
        )

    def goodbye(self, session: str) -> None:
        self._stop_live()
        self.console.print()
        self.console.print(Text(_GCODE_LOGO, style="bold bright_green"))
        self.console.print(
            "[dim green]Thanks for coding with GCode.\nKeep building. Keep shipping.[/dim green]"
        )
        self.console.print(
            Rule(f"[green]session[/green] [dim]::[/dim] [bold green]{session}[/bold green]")
        )

    def _show_slash_menu(self) -> str:
        """Show an interactive slash command menu with arrow key navigation.

        Returns the selected command string (e.g. '/help').
        """
        choices = [f"{cmd}  — {desc}" for cmd, desc in _SLASH_COMMANDS]

        try:
            selected = questionary.select(
                "Select a command:",
                choices=choices,
                use_shortcuts=False,
                instruction="(↑↓ navigate, Enter select, Esc cancel)",
            ).ask()
        except KeyboardInterrupt:
            return ""

        if selected is None:
            return ""

        cmd = selected.split()[0]
        return cmd

    def prompt(self) -> str:
        """Prompt the user for input.

        A bare ``/`` (on its own line) opens the interactive command menu.
        Any other input — including typed slash commands such as
        ``/model deepseek/deepseek-chat:free`` — is returned as-is for normal
        handling, so slash commands never have their arguments swallowed.
        """
        session: PromptSession[str] = PromptSession(
            enable_open_in_editor=False,
            enable_system_prompt=False,
            enable_history_search=False,
        )

        # Flush any pending Rich output so prompt_toolkit can take
        # control of the terminal cleanly (avoids cursor appearing
        # before the prompt).
        self.console.file.flush()
        line = session.prompt(
            HTML("<ansibold><ansicyan>You:</ansicyan></ansibold> "),
            mouse_support=False,
        )
        if line.strip() == "/":
            return self._show_slash_menu()

        return line

    # -- streaming assistant text -----------------------------------------
    def assistant_start(self) -> None:
        self._buffer = ""
        self._last_len = 0
        self._live = Live(
            Spinner("dots", text="Thinking…"),
            console=self.console,
            refresh_per_second=15,
            vertical_overflow="visible",
        )
        self._live.start()

    def token(self, text: str) -> None:
        if self._live is None:
            return
        self._buffer += text
        if len(self._buffer) - self._last_len >= _TRUNCATE_STEP:
            self._live.update(Markdown(self._buffer))
            self._last_len = len(self._buffer)

    def assistant_end(self) -> None:
        if self._live is None:
            return
        # Render the final (possibly empty) text, then freeze the live region.
        self._live.update(Markdown(self._buffer) if self._buffer else Text(""))
        self._live.stop()
        self._live = None
        self.console.print()

    # -- tool calls --------------------------------------------------------
    def tool_start(self, name: str, args: dict) -> None:
        summary = _summarize_tool(name, args)
        self.console.print(f"  [dim]⏺[/] [bold cyan]{name}[/] [dim]({summary})[/]")

    def ask_permission(self, prompt: str = "Allow?") -> bool:
        self.console.print(f"  [yellow]{prompt} (y/n):[/] ", end="")
        try:
            ans = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return ans in ("y", "yes")

    def tool_result(self, name: str, result: str) -> None:
        preview = _truncate(result, 600)
        self.console.print(f"  [dim]✓ {name}:[/] [dim]{escape(preview)}[/]")

    # -- status / errors ---------------------------------------------------
    def error(self, msg: str) -> None:
        self._stop_live()
        self.console.print(f"[red]✗ {escape(msg)}[/]")

    def info(self, msg: str) -> None:
        self._stop_live()
        self.console.print(msg)

    def print(self, *args, **kwargs) -> None:
        self._stop_live()
        self.console.print(*args, **kwargs)

    def _stop_live(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
