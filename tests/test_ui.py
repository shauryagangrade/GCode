from unittest.mock import Mock, patch

from gcode.ui import _SLASH_COMMANDS, RichUI
from rich.console import Console


def _select_mock(return_value):
    """Return a questionary.select() mock whose .ask() yields return_value."""
    fake_q = Mock()
    fake_q.ask.return_value = return_value
    return patch("gcode.ui.questionary.select", return_value=fake_q), fake_q


def test_goodbye_renders_logo_and_session():
    ui = RichUI()
    ui.console = Console(record=True, width=120)

    ui.goodbye("demo-session")

    output = ui.console.export_text()
    assert "██████╗" in output
    assert "Thanks for coding with GCode." in output
    assert "session" in output.lower()
    assert "demo-session" in output


def test_slash_menu_enables_type_to_filter():
    """The slash menu turns on questionary's as-you-type search filter.

    Typing narrows the choices (e.g. "oll" filters to /ollama), while arrow
    keys, Enter, and Esc keep working. j/k must be disabled because questionary
    rejects combining them with the search filter.
    """
    ui = RichUI()
    patcher, _ = _select_mock("/ollama  — List/select local Ollama models")
    with patcher as mock_select:
        selected = ui._show_slash_menu()

    assert selected == "/ollama"
    kwargs = mock_select.call_args.kwargs
    assert kwargs["use_search_filter"] is True
    assert kwargs["use_jk_keys"] is False
    assert kwargs["use_shortcuts"] is False


def test_slash_menu_cancel_returns_empty():
    """Esc (None result) or Ctrl+C returns "" so the prompt loop continues."""
    ui = RichUI()

    patcher, _ = _select_mock(None)
    with patcher:
        assert ui._show_slash_menu() == ""

    with patch("gcode.ui.questionary.select", side_effect=KeyboardInterrupt):
        assert ui._show_slash_menu() == ""


def test_slash_menu_choice_labels_are_searchable():
    """Choice labels include the command name so a substring match filters.

    The full label is "{cmd}  — {desc}"; filtering on "oll" must keep the
    /ollama entry (and anything else containing the substring).
    """
    labels = [f"{cmd}  — {desc}" for cmd, desc in _SLASH_COMMANDS]
    filtered = [label for label in labels if "oll" in label.lower()]
    assert any("/ollama" in label for label in filtered)
    assert len(filtered) >= 1


def test_slash_menu_all_commands_parse_to_first_token():
    """Every selected label maps back to exactly its command name."""
    for cmd, desc in _SLASH_COMMANDS:
        label = f"{cmd}  — {desc}"
        assert label.split()[0] == cmd
