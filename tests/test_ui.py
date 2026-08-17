from unittest.mock import Mock, patch

from gcode.ui import RichUI, _summarize_tool, _truncate
from rich.console import Console


def test_goodbye_renders_logo_and_session():
    ui = RichUI()
    ui.console = Console(record=True, width=120)

    ui.goodbye("demo-session")

    output = ui.console.export_text()
    assert "██████╗" in output
    assert "Thanks for coding with GCode." in output
    assert "session" in output.lower()
    assert "demo-session" in output


# -- _truncate -------------------------------------------------------------


def test_truncate_short_text_unchanged():
    assert _truncate("hello world", 50) == "hello world"


def test_truncate_normalizes_whitespace():
    assert _truncate("a   b\n\tc", 50) == "a b c"


def test_truncate_long_text_appends_ellipsis():
    out = _truncate("x" * 100, 80)
    assert out == "x" * 80 + "…"


def test_truncate_exact_limit_no_ellipsis():
    assert _truncate("x" * 80, 80) == "x" * 80


def test_truncate_empty_string():
    assert _truncate("", 10) == ""


def test_truncate_non_string_input():
    assert _truncate(42, 10) == "42"


# -- _summarize_tool -------------------------------------------------------


def test_summarize_tool_execute_bash_command():
    assert _summarize_tool("execute_bash", {"command": "ls -la"}) == "ls -la"


def test_summarize_tool_uses_path_when_present():
    assert _summarize_tool("read_file", {"path": "src/main.py"}) == "src/main.py"


def test_summarize_tool_non_string_path_becomes_empty():
    assert _summarize_tool("read_file", {"path": 123}) == ""


def test_summarize_tool_path_wins_over_other_args():
    assert _summarize_tool("grep", {"pattern": "foo", "path": "src"}) == "src"


def test_summarize_tool_empty_args():
    assert _summarize_tool("noop", {}) == ""


def test_summarize_tool_truncates_long_values():
    out = _summarize_tool("edit_file", {"path": "x" * 500})
    assert out == "x" * 120 + "…"


# -- _show_slash_menu ------------------------------------------------------


def _mock_select(return_value):
    sel = Mock()
    sel.ask.return_value = return_value
    return sel


def test_slash_menu_returns_selected_command():
    with patch(
        "gcode.ui.questionary.select",
        return_value=_mock_select("/help  — Show available commands"),
    ) as select_mock:
        ui = RichUI()
        assert ui._show_slash_menu() == "/help"

    choices = select_mock.call_args.kwargs["choices"]
    assert choices[0].startswith("/help")


def test_slash_menu_cancel_returns_empty():
    with patch("gcode.ui.questionary.select", return_value=_mock_select(None)):
        ui = RichUI()
        assert ui._show_slash_menu() == ""


def test_slash_menu_keyboard_interrupt_returns_empty():
    sel = Mock()
    sel.ask.side_effect = KeyboardInterrupt
    with patch("gcode.ui.questionary.select", return_value=sel):
        ui = RichUI()
        assert ui._show_slash_menu() == ""


# -- streaming refresh handler ---------------------------------------------


class _FakeLive:
    """Minimal stand-in for rich.live.Live that records updates."""

    def __init__(self):
        self.updates = []
        self.stopped = False

    def start(self):
        pass

    def update(self, content):
        self.updates.append(content)

    def stop(self):
        self.stopped = True


def test_token_renders_markdown_after_threshold(monkeypatch):
    from gcode import ui as ui_module

    fake = _FakeLive()
    monkeypatch.setattr(ui_module, "Live", lambda *args, **kwargs: fake)

    ui = RichUI()
    ui.assistant_start()

    # Below the 80-char re-render threshold: no update yet.
    ui.token("x" * 40)
    assert fake.updates == []

    # Crossing the threshold triggers one Markdown update.
    ui.token("y" * 50)  # total 90 >= 80
    assert len(fake.updates) == 1

    # Ending the stream renders the final text and stops the live region.
    ui.assistant_end()
    assert fake.stopped
    assert len(fake.updates) == 2


# -- tool display ----------------------------------------------------------


def test_tool_start_renders_summary():
    ui = RichUI()
    ui.console = Console(record=True, width=120)

    ui.tool_start("execute_bash", {"command": "ls"})

    output = ui.console.export_text()
    assert "execute_bash" in output
    assert "ls" in output
