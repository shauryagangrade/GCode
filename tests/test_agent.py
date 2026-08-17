"""Unit tests for the agent loop, focused on Ctrl+C interrupt handling."""

from unittest.mock import Mock, patch

from gcode.agent import _run_tool, _stream
from langchain_core.messages import AIMessage, AIMessageChunk


class _FakeUI:
    """Minimal UI stub recording calls for the streaming paths under test."""

    def __init__(self):
        self.calls = []

    def assistant_start(self):
        self.calls.append("assistant_start")

    def token(self, text):
        self.calls.append(("token", text))

    def assistant_end(self):
        self.calls.append("assistant_end")

    def info(self, msg):
        self.calls.append(("info", msg))


class _InterruptingModel:
    """A model whose stream yields one chunk and then raises KeyboardInterrupt."""

    def stream(self, messages):
        yield AIMessageChunk(content="partial reply ")
        raise KeyboardInterrupt


class _ToolRaisingInterrupt:
    def invoke(self, tool_args):
        raise KeyboardInterrupt


def test_stream_keeps_partial_text_on_keyboard_interrupt():
    ui = _FakeUI()
    msg = _stream([], _InterruptingModel(), ui)

    assert isinstance(msg, AIMessage)
    assert msg.content == "partial reply "
    # No half-formed tool calls are carried into history after an interrupt.
    assert msg.tool_calls == []
    assert ("info", "(streaming stopped by user)") in ui.calls
    assert "assistant_end" in ui.calls


def test_stream_interrupt_with_no_chunks_yet():
    class _ImmediateInterrupt:
        def stream(self, messages):
            raise KeyboardInterrupt

    ui = _FakeUI()
    msg = _stream([], _ImmediateInterrupt(), ui)

    assert isinstance(msg, AIMessage)
    assert msg.content == ""
    assert msg.tool_calls == []
    assert ("info", "(streaming stopped by user)") in ui.calls


def test_run_tool_returns_cancelled_on_keyboard_interrupt():
    ui = Mock()
    with patch("gcode.agent.TOOL_MAP", {"failing_tool": _ToolRaisingInterrupt()}):
        result = _run_tool("failing_tool", {}, ui)

    assert result == "Command execution cancelled by user."
    ui.tool_result.assert_called_once_with("failing_tool", "Command execution cancelled by user.")
