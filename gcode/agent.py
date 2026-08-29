"""GCode agent: model construction, the streaming tool-call loop, history trim."""

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from gcode.errors import format_model_error
from gcode.ollama import OLLAMA_V1_URL
from gcode.tools import TOOL_MAP, is_auto_approve

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_HISTORY = 30


def _usage_value(usage: dict, *names):
    """Return the first non-None value among the given keys, so zero counts win."""
    for name in names:
        if usage.get(name) is not None:
            return usage[name]
    return None


def _print_usage(response, ui) -> None:
    """Print a compact footer with token usage when the provider supplies it.

    Prefers LangChain's ``usage_metadata`` and falls back to
    ``response_metadata['token_usage' | 'usage']``. Prints nothing when no
    usage is available and never raises.
    """
    try:
        usage = getattr(response, "usage_metadata", None)
        if not isinstance(usage, dict) or all(v is None for v in usage.values()):
            meta = getattr(response, "response_metadata", {}) or {}
            cand: dict = {}
            if isinstance(meta, dict):
                cand = meta.get("token_usage") or meta.get("usage") or {}
            usage = cand if isinstance(cand, dict) else None
        if not usage or all(v is None for v in usage.values()):
            return
        inp = _usage_value(usage, "input_tokens", "prompt_tokens", "promptTokens")
        out = _usage_value(usage, "output_tokens", "completion_tokens", "completionTokens")
        total = _usage_value(usage, "total_tokens", "totalTokens")
        parts = []
        if inp is not None and out is not None:
            parts.append(f"{inp} in / {out} out")
        elif inp is not None:
            parts.append(f"{inp} in")
        elif out is not None:
            parts.append(f"{out} out")
        if total is not None:
            parts.append(f"total {total}")
        cost = _usage_value(usage, "cost", "total_cost")
        if cost is not None:
            try:
                parts.append(f"~${float(cost):.4f}")
            except (TypeError, ValueError):
                parts.append(f"cost {cost}")
        if parts:
            ui.info(f"[dim]Usage: {'  ·  '.join(parts)}[/dim]")
    except Exception:
        return


def build_model(model_id: str, api_key: str):
    """Build a ChatOpenAI model bound to all GCode tools.

    Supports both OpenRouter (requires api_key) and local Ollama (api_key can
    be empty).  Ollama model ids are prefixed with ``ollama/`` (e.g.
    ``ollama/llama3.2``); the prefix is stripped when talking to the local
    server.
    """
    from gcode.tools import ALL_TOOLS

    # Ollama local models — no API key required
    # Ollama's OpenAI-compatible endpoint ignores the API key field, so we
    # pass a non-empty placeholder to satisfy ChatOpenAI's validation.
    if model_id.startswith("ollama/"):
        ollama_model = model_id[len("ollama/") :]  # strip prefix
        return ChatOpenAI(
            model=ollama_model,
            api_key=SecretStr("ollama"),
            base_url=OLLAMA_V1_URL,
        ).bind_tools(ALL_TOOLS)

    # Default: OpenRouter
    return ChatOpenAI(
        model=model_id,
        api_key=SecretStr(api_key),
        base_url=OPENROUTER_BASE_URL,
    ).bind_tools(ALL_TOOLS)


MAX_HISTORY_TOKENS = 12000  # approx budget for ~30 messages at ~400 tokens each


def _estimate_tokens(msg) -> int:
    """Heuristic token estimate for a message (len//4), with tiktoken if available."""
    try:
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            # Content may be a list of parts (e.g., for tool calls)
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        else:
            text = str(content) if content else ""
        # Include tool_calls in estimate
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            text += str(tool_calls)
        # Try tiktoken if installed for more accurate count
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 4)  # tiktoken unavailable: heuristic
    except Exception:
        return 100  # fallback small budget


def trim_history(messages: list) -> None:
    """Keep history within message-count and token-budget limits.

    Preserves the system message plus the most recent messages that fit within
    ``MAX_HISTORY`` and ``MAX_HISTORY_TOKENS``. Trims only at a settled
    boundary and drops any leading ToolMessages whose owning assistant was
    trimmed, so the API never sees an orphaned tool result. A single huge
    tool output is capped at the source (see :func:`gcode.tools.grep`).
    """
    if len(messages) <= 1:
        return
    # Fast path: within both limits
    if len(messages) <= MAX_HISTORY + 1:
        total = sum(_estimate_tokens(m) for m in messages)
        if total <= MAX_HISTORY_TOKENS:
            return
    # Need to trim: keep system message + most recent that fit
    # Start from most recent and build backwards within budget
    system = messages[0]
    rest = messages[1:]
    # Enforce count limit first, then token budget
    if len(rest) > MAX_HISTORY:
        rest = rest[-MAX_HISTORY:]
        # Drop leading ToolMessages that would be orphaned
        while rest and isinstance(rest[0], ToolMessage):
            rest.pop(0)
    # Enforce token budget by dropping oldest while over budget.
    # Keep at least one recent turn (2 messages) if possible.
    while len(rest) > 2:
        if sum(_estimate_tokens(m) for m in [system] + rest) <= MAX_HISTORY_TOKENS:
            break
        dropped = rest.pop(0)
        # Dropping an AIMessage that issued tool calls orphans its ToolMessages.
        if getattr(dropped, "tool_calls", None):
            while rest and isinstance(rest[0], ToolMessage):
                rest.pop(0)
    # Final orphan check: ensure rest doesn't start with ToolMessage
    while rest and isinstance(rest[0], ToolMessage):
        rest.pop(0)
    messages[:] = [system] + rest


def _stream(messages: list, model, ui) -> AIMessage:
    """Stream one model response, forwarding text to the UI, and return the
    accumulated message (with ``tool_calls`` populated).

    A Ctrl+C during streaming stops the stream but keeps the session alive:
    whatever was accumulated so far is returned as the turn's assistant
    message so it gets persisted with the rest of the history.
    """
    ui.assistant_start()
    accumulated = None
    interrupted = False
    try:
        for chunk in model.stream(messages):
            if not isinstance(chunk, AIMessageChunk):
                continue
            if chunk.content:
                ui.token(chunk.content)
            accumulated = chunk if accumulated is None else accumulated + chunk
    except KeyboardInterrupt:
        interrupted = True
    if accumulated is None:
        accumulated = AIMessageChunk(content="")
    ui.assistant_end()
    if interrupted:
        ui.info("(streaming stopped by user)")
    # Store the canonical AIMessage (not the chunk) for clean history + reloads.
    # usage_metadata/response_metadata carry the provider's token counts, which
    # _print_usage reads; dropping them would make the usage footer always empty.
    return AIMessage(
        content=accumulated.content,
        tool_calls=[] if interrupted else accumulated.tool_calls,
        additional_kwargs=accumulated.additional_kwargs,
        response_metadata=accumulated.response_metadata,
        usage_metadata=accumulated.usage_metadata,
        id=accumulated.id,
    )


def _run_tool(tool_name: str, tool_args: dict, ui) -> str:
    ui.tool_start(tool_name, tool_args)
    if tool_name == "execute_bash" and not is_auto_approve():
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
        except KeyboardInterrupt:
            # Ctrl+C during a tool call cancels that call and keeps the
            # session alive; the model sees a cancelled result instead of the
            # whole REPL dying.
            result = "Command execution cancelled by user."
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
    _print_usage(response, ui)

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
        _print_usage(response, ui)

    if errored:
        return
