from rich.console import Console

from gcode.ui import RichUI


def test_goodbye_renders_logo_and_session():
    ui = RichUI()
    ui.console = Console(record=True, width=120)

    ui.goodbye("demo-session")

    output = ui.console.export_text()
    assert "██████╗" in output
    assert "Thanks for coding with GCode." in output
    assert "session" in output.lower()
    assert "demo-session" in output
