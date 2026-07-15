"""Rich-based terminal UI for GCode, mimicking the Claude Code look.

A single ``RichUI`` wraps a ``rich.console.Console`` and exposes hooks the agent
loop calls: streaming assistant text (spinner -> live Markdown), tool-call
display, a permission gate, and status/error output.
"""

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text

_TRUNCATE_STEP = 80  # re-render Markdown only after this many new characters


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
        return _truncate(args.get("path"), 120)
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

    def prompt(self) -> str:
        self.console.print("[bold cyan]You:[/] ", end="")
        return input()

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
        self.console.print(f"  [dim]✓ {name}:[/] [dim]{preview}[/]")

    # -- status / errors ---------------------------------------------------
    def error(self, msg: str) -> None:
        self._stop_live()
        self.console.print(f"[red]✗ {msg}[/]")

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
