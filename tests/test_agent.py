"""Unit tests for the agent loop: Ctrl+C interrupts and the usage footer."""

from unittest.mock import Mock, patch

from gcode.agent import _print_usage, _run_tool, _stream
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


class _UsageModel:
    """A model whose final stream chunk carries the provider's usage metadata."""

    def stream(self, messages):
        yield AIMessageChunk(content="hi")
        yield AIMessageChunk(
            content="",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )


def test_stream_preserves_usage_metadata():
    ui = _FakeUI()
    msg = _stream([], _UsageModel(), ui)

    assert msg.usage_metadata == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def test_print_usage_from_usage_metadata():
    ui = _FakeUI()
    msg = AIMessage(
        content="", usage_metadata={"input_tokens": 842, "output_tokens": 128, "total_tokens": 970}
    )

    _print_usage(msg, ui)

    assert ("info", "[dim]Usage: 842 in / 128 out  ·  total 970[/dim]") in ui.calls


def test_print_usage_falls_back_to_response_metadata():
    ui = _FakeUI()
    msg = AIMessage(
        content="",
        response_metadata={
            "token_usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
        },
    )

    _print_usage(msg, ui)

    assert ("info", "[dim]Usage: 3 in / 4 out  ·  total 7[/dim]") in ui.calls


def test_print_usage_keeps_zero_counts():
    ui = _FakeUI()
    msg = AIMessage(
        content="",
        response_metadata={
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 7, "total_tokens": 7}
        },
    )

    _print_usage(msg, ui)

    assert ("info", "[dim]Usage: 0 in / 7 out  ·  total 7[/dim]") in ui.calls


def test_print_usage_shows_cost_when_present():
    ui = _FakeUI()
    msg = AIMessage(
        content="",
        response_metadata={
            "token_usage": {
                "prompt_tokens": 3,
                "completion_tokens": 4,
                "total_tokens": 7,
                "total_cost": 0.0123456,
            }
        },
    )

    _print_usage(msg, ui)

    assert ("info", "[dim]Usage: 3 in / 4 out  ·  total 7  ·  ~$0.0123[/dim]") in ui.calls


def test_print_usage_silent_without_usage():
    ui = _FakeUI()

    _print_usage(AIMessage(content="no usage here"), ui)

    assert not any(call[0] == "info" for call in ui.calls if isinstance(call, tuple))


# -- trim_history -------------------------------------------------------------


def test_trim_history_keeps_too_many_small_messages():
    from gcode.agent import MAX_HISTORY, trim_history
    from langchain_core.messages import HumanMessage

    msgs = [HumanMessage(content=f"m{i}") for i in range(MAX_HISTORY + 5)]
    system = HumanMessage(content="system")
    history = [system] + msgs

    trim_history(history)

    assert history[0] is system
    assert len(history) == MAX_HISTORY + 1


def test_trim_history_trims_by_token_budget_not_count():
    from gcode.agent import MAX_HISTORY_TOKENS, trim_history
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    system = HumanMessage(content="system")
    # Varied text so the estimate is over budget whether tiktoken or len//4 is used
    # (pure "-xxxxxxxx" compresses to almost nothing under BPE).
    big = " ".join(f"term{i}" for i in range(MAX_HISTORY_TOKENS * 4))
    history = [
        system,
        HumanMessage(content="turn one"),
        AIMessage(
            content="",
            tool_calls=[{"name": "grep", "args": {}, "id": "call_1", "type": "tool_call"}],
        ),
        ToolMessage(content=big, tool_call_id="call_1"),
        HumanMessage(content="turn two"),
        AIMessage(content="reply"),
    ]

    trim_history(history)

    # The oversized turn is dropped entirely (no orphaned ToolMessage).
    assert history[0] is system
    assert history[-1].content == "reply"
    assert not any(isinstance(m, ToolMessage) for m in history)
    assert len(history) <= 4


def test_trim_history_orphaned_tool_messages_dropped():
    from gcode.agent import MAX_HISTORY, MAX_HISTORY_TOKENS, trim_history
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    system = HumanMessage(content="system")
    # Keep enough short messages that the count limit (not the token budget) trims,
    # and make the kept tail begin with ToolMessages whose owner was trimmed out.
    rest = [
        AIMessage(
            content="",
            tool_calls=[{"name": "grep", "args": {}, "id": "call_1", "type": "tool_call"}],
        ),
        ToolMessage(content="res1", tool_call_id="call_1"),
        ToolMessage(content="res2", tool_call_id="call_1"),
    ] + [HumanMessage(content=f"m{i}") for i in range(MAX_HISTORY)]
    history = [system] + rest
    small = sum(len(m.content) for m in history)
    assert small <= MAX_HISTORY_TOKENS * 4  # token budget not the deciding factor

    trim_history(history)

    assert history[0] is system
    assert len(history) <= MAX_HISTORY + 1
    assert not any(isinstance(m, ToolMessage) for m in history)
    assert not getattr(history[1], "tool_calls", None)
    assert history[1].content == "m0"
