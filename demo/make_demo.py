#!/usr/bin/env python3.13
"""Generate a scripted demo GIF for GCode.

This does NOT call a real LLM. It replays a realistic GCode session by
reusing GCode's *exact* visual language (the same Rich markup found in
``gcode/ui.py``): cyan banner, cyan ``You:`` prompt, cyan ``⏺ tool(args)``
lines, dim ``✓ tool: …`` results, the yellow bash ``y/n`` gate, and token
-by-token streaming. Each tick re-renders the full screen to a virtual
terminal (pyte) and is exported as a PNG frame; ffmpeg then encodes the
frames into ``../docs/demo.gif``.

Requires: pip install pyte pillow  (rich comes with gcode)
Run:        python3.13 demo/make_demo.py
Output:      docs/demo.gif
"""

import os
import time

import pyte
from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.terminal_theme import TerminalTheme

# --------------------------------------------------------------------------
# Terminal / frame config
# --------------------------------------------------------------------------
COLS, ROWS = 96, 30
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
FONT_SIZE = 18
BG = (20, 22, 28)  # near-black, matches a dark terminal
FG = (210, 214, 222)
SCALE = 2  # supersample for crispness
CPS = 90  # characters per second typed
STREAM_CPS = 220  # streaming token speed
GATE_FRAMES = 14  # frames the y/n gate stays on screen
IDLE_FRAMES = 10  # pause between blocks

# GCode's real palette (see gcode/ui.py + gcode/cli.py)
CYAN = "#22d3ee"
DIM = "#7c8794"
YELLOW = "#facc15"
RED = "#f87171"
WHITE = "#e6e9ef"

# A 16-colour theme so Rich markup maps onto clean VT colours.
THEME = TerminalTheme(
    background=BG,
    foreground=FG,
    normal=[
        FG,
        "#f87171",
        CYAN,
        YELLOW,
        "#a3e635",
        "#38bdf8",
        "#c084fc",
        "#e2e8f0",
        DIM,
        "#fca5a5",
        "#67e8f9",
        "#fde047",
        "#bef264",
        "#7dd3fc",
        "#d8b4fe",
        "#f8fafc",
    ],
    bright=[
        FG,
        "#f87171",
        CYAN,
        YELLOW,
        "#a3e635",
        "#38bdf8",
        "#c084fc",
        "#e2e8f0",
        DIM,
        "#fca5a5",
        "#67e8f9",
        "#fde047",
        "#bef264",
        "#7dd3fc",
        "#d8b4fe",
        "#f8fafc",
    ],
)

# --------------------------------------------------------------------------
# Virtual terminal + frame capture
# --------------------------------------------------------------------------
screen = pyte.Screen(COLS, ROWS)
stream = pyte.ByteStream(screen)

console = Console(
    file=None,
    width=COLS,
    height=ROWS,
    legacy_windows=False,
    color_system="truecolor",
    record=True,
)


def render_to_screen(markup: str) -> None:
    """Render a Rich markup string into the pyte screen's scrollback."""
    screen.reset()
    with console.capture() as cap:
        console.print(markup, end="")
    out = cap.get().replace("\n", "\r\n")
    stream.feed(out.encode("utf-8", "replace"))


def screen_to_image() -> Image.Image:
    """Render the current pyte screen to a PNG Image (cropped to used rows)."""
    # Build a text grid + per-cell colour grid from pyte.
    # pyte buffer is a defaultdict keyed by row index (0..ROWS-1); each row
    # is itself a mapping keyed by column index (0..COLS-1) -> Char namedtuple.
    lines = []
    for r in range(ROWS):
        row = screen.buffer[r]
        line = []
        for c in range(COLS):
            cell = row[c]
            ch = cell.data if cell.data != " " else " "
            fg = cell.fg if cell.fg and cell.fg != "default" else None
            bg = cell.bg if cell.bg and cell.bg != "default" else None
            line.append((ch, fg, bg))
        lines.append(line)

    # Determine how many rows are actually used.
    used_rows = ROWS
    for r in range(ROWS - 1, -1, -1):
        if any(c[0] not in ("", " ") for c in lines[r]):
            used_rows = r + 1
            break

    cw, ch = (
        FONT_SIZE * 0 + 11 * SCALE,
        int(FONT_SIZE * 1.5 * SCALE),
    )  # monospace metrics
    # measure via font
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE * SCALE)
    cw = int(font.getlength("M")) + 1
    ch = int(FONT_SIZE * SCALE * 1.5)

    img = Image.new("RGB", (COLS * cw, used_rows * ch), BG)
    draw = ImageDraw.Draw(img)

    for r in range(used_rows):
        for c in range(COLS):
            ch_ch, fg, bg = lines[r][c]
            if ch_ch in ("", " "):
                continue
            x = c * cw
            y = r * ch
            if bg:
                try:
                    draw.rectangle([x, y, x + cw, y + ch], fill=bg)
                except Exception:
                    pass
            color = fg or "#d2d6de"
            try:
                draw.text((x, y), ch_ch, font=font, fill=color)
            except Exception:
                pass
    return img


# --------------------------------------------------------------------------
# Frame management
# --------------------------------------------------------------------------
FRAMES = []
FRAME_DIR = os.path.join(os.path.dirname(__file__), "frames")


def snap(note: str = "") -> None:
    img = screen_to_image()
    path = os.path.join(FRAME_DIR, f"frame_{len(FRAMES):05d}.png")
    img.save(path)
    FRAMES.append(path)
    if note:
        print(f"  frame {len(FRAMES):03d}: {note}")


def hold(frames: int, note: str = "") -> None:
    for _ in range(frames):
        snap(note)


def type_line(markup_prefix: str, text: str, color=CYAN, cps=CPS) -> None:
    """Type ``text`` after ``markup_prefix`` prompt, character by character."""
    acc = ""
    for i, ch in enumerate(text):
        acc = text[: i + 1]
        render_to_screen(markup_prefix + f"[{color}]{acc}[/]")
        snap()
        time.sleep(1.0 / cps)


# --------------------------------------------------------------------------
# Scenario
# --------------------------------------------------------------------------
def build_scenario() -> None:
    os.makedirs(FRAME_DIR, exist_ok=True)

    # 1) Banner + intro
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: qwen/qwen3-coder:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]"
    )
    snap("banner")
    hold(IDLE_FRAMES)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: qwen/qwen3-coder:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]Type /help for commands. Ctrl-D or /quit to exit.[/]"
    )
    snap("intro")
    hold(IDLE_FRAMES)

    # 2) /help
    type_line("[cyan bold]You:[/] ", "/help")
    hold(6)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: qwen/qwen3-coder:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]Type /help for commands. Ctrl-D or /quit to exit.[/]\n"
        "[cyan bold]You:[/] [cyan]/help[/]\n"
        "[dim]GCode slash commands:\n"
        "  /help            Show this help\n"
        "  /models          List available free models\n"
        "  /model <id|#n>   Switch to a model (id, or #n index from /models)\n"
        "  /history         Show recent conversation turns\n"
        "  /status          Show quick git status\n"
        "  /clear           Start a fresh session (discard history)\n"
        "  /quit, /exit     Leave GCode[/]"
    )
    snap("/help output")
    hold(IDLE_FRAMES)

    # 3) /models
    type_line("[cyan bold]You:[/] ", "/models")
    hold(6)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: qwen/qwen3-coder:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]/models[/]\n"
        "[dim]Available free models (use '/model <id>' or '/model #n'):[/]\n"
        "[dim]  1. qwen/qwen3-coder:free\n"
        "  2. deepseek/deepseek-chat-v3-0324:free\n"
        "  3. meta-llama/llama-3.3-70b-instruct:free\n"
        "  4. google/gemini-2.0-flash-exp:free[/]"
    )
    snap("/models output")
    hold(IDLE_FRAMES)

    # 4) /model #2
    type_line("[cyan bold]You:[/] ", "/model #2")
    hold(6)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: qwen/qwen3-coder:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]/model #2[/]\n"
        "[cyan]Switched to model: deepseek/deepseek-chat-v3-0324:free[/]"
    )
    snap("/model switch")
    hold(IDLE_FRAMES)

    # helper to show a streamed assistant reply + a tool call
    def agent_turn(prompt_text, assistant_text, tool_name, tool_args, tool_result):
        type_line("[cyan bold]You:[/] ", prompt_text)
        hold(6)
        # streamed reply
        acc = ""
        for i in range(0, len(assistant_text), 3):
            acc = assistant_text[: i + 3]
            render_to_screen(
                f"[cyan]── GCode v0.1.0   model: deepseek/…:free   "
                f"cwd: ~/Projects/GCode   session: demo ──[/]\n"
                f"[dim]…(prior turns)…[/]\n"
                f"[cyan bold]You:[/] [cyan]{prompt_text}[/]\n"
                f"[cyan]⠿ Thinking…[/]\n"
                f"[white]{acc}[/]"
            )
            snap()
            time.sleep(1.0 / STREAM_CPS)
        # final reply + tool call
        render_to_screen(
            f"[cyan]── GCode v0.1.0   model: deepseek/…:free   "
            f"cwd: ~/Projects/GCode   session: demo ──[/]\n"
            f"[dim]…(prior turns)…[/]\n"
            f"[cyan bold]You:[/] [cyan]{prompt_text}[/]\n"
            f"[white]{assistant_text}[/]\n"
            f"[dim]⏺[/] [cyan]{tool_name}[/] [dim]({tool_args})[/]"
        )
        snap(f"tool {tool_name}")
        hold(8)
        render_to_screen(
            f"[cyan]── GCode v0.1.0   model: deepseek/…:free   "
            f"cwd: ~/Projects/GCode   session: demo ──[/]\n"
            f"[dim]…(prior turns)…[/]\n"
            f"[cyan bold]You:[/] [cyan]{prompt_text}[/]\n"
            f"[white]{assistant_text}[/]\n"
            f"[dim]⏺[/] [cyan]{tool_name}[/] [dim]({tool_args})[/]\n"
            f"[dim]✓ {tool_name}:[/] [dim]{tool_result}[/]"
        )
        snap(f"result {tool_name}")
        hold(IDLE_FRAMES)

    # 5) write_file
    agent_turn(
        "create a file demo.py that prints a greeting",
        "Sure — I'll write demo.py with a small greeting program.",
        "write_file",
        "demo.py",
        "Wrote 48 bytes to demo.py",
    )

    # 6) edit_file
    agent_turn(
        "now make it also print the current time",
        "I'll edit demo.py to add a timestamp line.",
        "edit_file",
        "demo.py",
        "Edited demo.py (1 occurrence(s) replaced).",
    )

    # 7) git_status
    agent_turn(
        "show me the git status",
        "Here is the working tree status:",
        "git_status",
        ".",
        " M demo.py",
    )

    # 8) execute_bash — approved
    type_line("[cyan bold]You:[/] ", "run the script and show the output")
    hold(6)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]run the script and show the output[/]\n"
        "[white]Running it now:[/]\n"
        "[dim]⏺[/] [cyan]execute_bash[/] [dim](python demo.py)[/]\n"
        "[yellow]Run this command? (y/n):[/] "
    )
    snap("bash gate")
    hold(GATE_FRAMES)
    # type 'y'
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]run the script and show the output[/]\n"
        "[white]Running it now:[/]\n"
        "[dim]⏺[/] [cyan]execute_bash[/] [dim](python demo.py)[/]\n"
        "[yellow]Run this command? (y/n):[/] [white]y[/]"
    )
    snap("gate y")
    hold(8)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]run the script and show the output[/]\n"
        "[white]Running it now:[/]\n"
        "[dim]⏺[/] [cyan]execute_bash[/] [dim](python demo.py)[/]\n"
        "[yellow]Run this command? (y/n):[/] [white]y[/]\n"
        "[dim]✓ execute_bash:[/] [dim]Hello from GCode\n2026-07-16 14:32:08[/]"
    )
    snap("bash result")
    hold(IDLE_FRAMES)

    # 9) declined gate (demo the 'n' path)
    type_line("[cyan bold]You:[/] ", "delete the temp files")
    hold(6)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]delete the temp files[/]\n"
        "[white]I can run that:[/]\n"
        "[dim]⏺[/] [cyan]execute_bash[/] [dim](rm -f *.tmp)[/]\n"
        "[yellow]Run this command? (y/n):[/] "
    )
    snap("gate 2")
    hold(GATE_FRAMES)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]delete the temp files[/]\n"
        "[white]I can run that:[/]\n"
        "[dim]⏺[/] [cyan]execute_bash[/] [dim](rm -f *.tmp)[/]\n"
        "[yellow]Run this command? (y/n):[/] [white]n[/]"
    )
    snap("gate n")
    hold(8)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]delete the temp files[/]\n"
        "[white]I can run that:[/]\n"
        "[dim]⏺[/] [cyan]execute_bash[/] [dim](rm -f *.tmp)[/]\n"
        "[yellow]Run this command? (y/n):[/] [white]n[/]\n"
        "[dim]✓ execute_bash:[/] [dim]Command execution cancelled by user.[/]"
    )
    snap("declined result")
    hold(IDLE_FRAMES)

    # 10) /quit
    type_line("[cyan bold]You:[/] ", "/quit")
    hold(6)
    render_to_screen(
        "[cyan]── GCode v0.1.0   model: deepseek/…:free   "
        "cwd: ~/Projects/GCode   session: demo ──[/]\n"
        "[dim]…(prior turns)…[/]\n"
        "[cyan bold]You:[/] [cyan]/quit[/]\n"
        "[cyan]Goodbye.[/]"
    )
    snap("quit")
    hold(20)


def main() -> None:
    t0 = time.time()
    build_scenario()
    t1 = time.time()
    print(f"\nRendered {len(FRAMES)} frames in {t1 - t0:.1f}s")
    print(f"Frames dir: {FRAME_DIR}")


if __name__ == "__main__":
    main()
