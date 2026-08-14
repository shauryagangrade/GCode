import json
import os
from unittest.mock import patch

from gcode import history
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


def test_path_sanitization(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    path1 = history._path("normal_session")
    assert path1 == os.path.join(str(tmp_path), "normal_session.json")

    path2 = history._path("session/with/slashes & spaces!#$")
    assert path2 == os.path.join(str(tmp_path), "session_with_slashes___spaces___.json")
    assert os.path.exists(tmp_path)


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="Hello"),
        AIMessage(content="Hi there!"),
    ]
    history.save("test_session", messages)

    loaded = history.load("test_session")
    assert loaded is not None
    assert len(loaded) == 3
    assert isinstance(loaded[0], SystemMessage)
    assert loaded[0].content == "You are a helpful assistant."
    assert isinstance(loaded[1], HumanMessage)
    assert loaded[1].content == "Hello"
    assert isinstance(loaded[2], AIMessage)
    assert loaded[2].content == "Hi there!"


def test_save_and_load_tool_call_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    messages = [
        HumanMessage(content="Find the word foo"),
        AIMessage(
            content="",
            tool_calls=[{"name": "grep", "args": {"pattern": "foo"}, "id": "call_1"}],
        ),
        ToolMessage(content="foo found at line 1", tool_call_id="call_1"),
    ]
    history.save("tool_session", messages)

    loaded = history.load("tool_session")
    assert loaded is not None
    assert len(loaded) == 3
    assert isinstance(loaded[1], AIMessage)
    assert loaded[1].tool_calls[0]["name"] == "grep"
    assert loaded[1].tool_calls[0]["id"] == "call_1"
    assert isinstance(loaded[2], ToolMessage)
    assert loaded[2].tool_call_id == "call_1"


def test_save_and_load_default_session(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    messages = [HumanMessage(content="Default session msg")]
    history.save(history.DEFAULT_SESSION, messages)

    loaded = history.load()
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0].content == "Default session msg"


def test_load_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    result = history.load("non_existent_session")
    assert result is None


def test_load_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    filepath = history._path("corrupt_session")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("{ invalid json content ...")

    result = history.load("corrupt_session")
    assert result is None


def test_load_corrupt_json_warns_with_path(tmp_path, monkeypatch, capsys):
    """A corrupt session file must warn and name the path, not silently vanish."""
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    filepath = history._path("corrupt_warn_session")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("{ invalid json content ...")

    result = history.load("corrupt_warn_session")
    assert result is None
    err = capsys.readouterr().err
    assert filepath in err
    assert "corrupt" in err


def test_load_missing_file_no_warning(tmp_path, monkeypatch, capsys):
    """A missing session file stays silent (no history yet is not an error)."""
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    result = history.load("never_saved_session")
    assert result is None
    assert capsys.readouterr().err == ""


def test_load_invalid_message_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    filepath = history._path("invalid_msg_session")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([{"invalid_key": "no_type"}], f)

    result = history.load("invalid_msg_session")
    assert result is None


def test_clear_session(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    messages = [HumanMessage(content="Test")]
    history.save("to_clear", messages)
    assert os.path.isfile(history._path("to_clear"))

    history.clear("to_clear")
    assert not os.path.isfile(history._path("to_clear"))

    # Clearing non-existent session should be safe and not raise error
    history.clear("to_clear")


def test_clear_default_session(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    messages = [HumanMessage(content="Test")]
    history.save(history.DEFAULT_SESSION, messages)
    assert os.path.isfile(history._path(history.DEFAULT_SESSION))

    history.clear()
    assert not os.path.isfile(history._path(history.DEFAULT_SESSION))


def test_save_write_failure_resilience(tmp_path, monkeypatch, capsys):
    """A failed save must warn, never raise, and leave no partial session file."""
    monkeypatch.setattr(history, "BASE_DIR", str(tmp_path))
    messages = [HumanMessage(content="Test")]
    with patch("gcode.history.os.replace", side_effect=OSError("Disk full or permission denied")):
        # Should not raise exception
        history.save("fail_session", messages)

    path = history._path("fail_session")
    assert not os.path.isfile(path)  # no partial file at the real path
    leftovers = [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]
    assert leftovers == []  # temp file cleaned up
    err = capsys.readouterr().err
    assert "could not save session history" in err
    assert path in err
