from gcode.errors import (
    format_model_error,
    missing_api_key_message,
    network_error_message,
    unknown_model_message,
)


class _FakeExc:
    def __init__(self, body):
        self.body = body

    def __str__(self):
        return f"Error code: ... - {self.body!r}"


def test_format_429_with_raw_and_retry():
    body = {
        "error": {
            "message": "Provider returned error",
            "code": 429,
            "metadata": {
                "raw": "qwen/foo is temporarily rate-limited upstream.",
                "retry_after_seconds": 29,
            },
        }
    }
    out = format_model_error(_FakeExc(body))
    assert "qwen/foo is temporarily rate-limited upstream." in out
    assert "Retry after ~29s." in out
    assert out.startswith("[429]")
    # No raw JSON braces should leak into the message.
    assert "{" not in out and "}" not in out


def test_format_404_tool_use():
    body = {
        "error": {
            "message": "No endpoints found that support tool use.",
            "code": 404,
        }
    }
    out = format_model_error(_FakeExc(body))
    assert "No endpoints found that support tool use." in out
    assert out.startswith("[404]")
    assert "{" not in out


def test_format_fallback_to_str():
    out = format_model_error(ValueError("something broke"))
    assert out == "something broke"


def test_missing_api_key_message_suggests_setup_and_env():
    out = missing_api_key_message()
    assert "Run /setup" in out
    assert "OPENROUTER_API_KEY" in out
    assert "~/.gcode/.env" in out
    assert "openrouter.ai/keys" in out


def test_network_error_message_suggests_checks():
    out = network_error_message("fetch the OpenRouter model list", TimeoutError("timed out"))
    assert "Could not fetch the OpenRouter model list" in out
    assert "internet connection" in out
    assert "proxy settings" in out
    assert "timed out" in out


def test_unknown_model_message_suggests_models_command():
    out = unknown_model_message("gpt-4")
    assert "Unknown model: 'gpt-4'" in out
    assert "/models" in out
    assert "/model <full-id>" in out
    assert "qwen/qwen3-coder:free" in out
