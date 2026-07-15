"""GCode agent: model construction, the streaming tool-call loop, history trim."""

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from gcode.errors import format_model_error
from gcode.tools import AUTO_APPROVE, TOOL_MAP

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_HISTORY = 30


def build_model(model_id: str, api_key: str):
    """Build a ChatOpenAI model (via OpenRouter) bound to all GCode tools."""
    from gcode.tools import ALL_TOOLS

    return ChatOpenAI(
        model=model_id,
        openai_api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    ).bind_tools(ALL_TOOLS)


def trim_history(messages: list) -> None:
    """Keep the system message plus the most recent MAX_HISTORY messages.

    Trims only at a settled boundary (between turns) and drops any leading
    ToolMessages whose owning assistant message was trimmed, so the API never
    sees an orphaned tool result.
    """
    if len(messages) <= MAX_HISTORY + 1:
        return
    tail = messages[-MAX_HISTORY:]
    while tail and isinstance(tail[0], ToolMessage):
        tail.pop(0)
    messages[:] = [messages[0]] + tail


def _stream(messages: list, model, ui) -> AIMessageChunk:
    """Stream one model response, forwarding text to the UI, and return the
    accumulated message (with ``tool_calls`` populated)."""
    ui.assistant_start()
    accumulated = None
    for chunk in model.stream(messages):
        if not isinstance(chunk, AIMessageChunk):
            continue
        if chunk.content:
            ui.token(chunk.content)
        accumulated = chunk if accumulated is None else accumulated + chunk
    if accumulated is None:
        accumulated = AIMessageChunk(content="")
    ui.assistant_end()
    # Store the canonical AIMessage (not the chunk) for clean history + reloads.
    return AIMessage(
        content=accumulated.content,
        tool_calls=accumulated.tool_calls,
        additional_kwargs=accumulated.additional_kwargs,
        id=accumulated.id,
    )


def _run_tool(tool_name: str, tool_args: dict, ui) -> str:
    ui.tool_start(tool_name, tool_args)
    if tool_name == "execute_bash" and not AUTO_APPROVE:
        if not ui.ask_permission("Run this command?"):
            result = "Command execution cancelled by user."
            ui.tool_result(tool_name, result)
            return result
    fn = TOOL_MAP.get(tool_name)
    if fn is None:
        result = f"Unknown tool: {tool_name}"
    else:
        try:
            result = fn.invoke(tool_args)
        except Exception as exc:
            result = f"Tool {tool_name} raised: {exc}"
    ui.tool_result(tool_name, result)
    return result


def run_turn(user_input: str, messages: list, model, ui) -> None:
    """Run one user turn: append the human message, stream the response, loop
    over any tool calls (with UI display + a permission gate for bash), and
    append everything to ``messages``.
    """
    messages.append(HumanMessage(content=user_input))

    try:
        response = _stream(messages, model, ui)
    except Exception as exc:
        ui.error("model request failed: " + format_model_error(exc))
        return

    messages.append(response)

    errored = False
    while getattr(response, "tool_calls", None):
        for tool_call in response.tool_calls:
            result = _run_tool(tool_call["name"], tool_call["args"], ui)
            messages.append(
                ToolMessage(
                    content=result,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

        try:
            response = _stream(messages, model, ui)
        except Exception as exc:
            ui.error("model request failed: " + format_model_error(exc))
            errored = True
            break

        messages.append(response)

    if errored:
        return
