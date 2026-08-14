"""Tests for first-run key setup: validation, env loading, persistence.

These are the paths a new user hits before anything else works, and they were
untested. The HTTP matrix (200 / 401 / 403 / network) is mocked -- nothing here
reaches the network.

Every test that can write redirects ``_ENV_DIR`` and ``_ENV_FILE`` at the
module to a tmp_path first. Without that, running the suite would overwrite the
developer's real ``~/.gcode/.env``.
"""

from unittest.mock import Mock, patch

import pytest
import requests
from gcode import setup as gcode_setup
from gcode.setup import (
    _OPENAI_KEY,
    _OPENROUTER_KEY,
    get_api_key,
    load_env,
    save_api_key,
    validate_api_key,
)


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """Point the module's env-file constants at a throwaway directory."""
    directory = tmp_path / ".gcode"
    path = directory / ".env"
    monkeypatch.setattr(gcode_setup, "_ENV_DIR", directory)
    monkeypatch.setattr(gcode_setup, "_ENV_FILE", path)
    return path


@pytest.fixture(autouse=True)
def clean_key_env(monkeypatch):
    """No inherited key should decide the outcome of a precedence test."""
    monkeypatch.delenv(_OPENROUTER_KEY, raising=False)
    monkeypatch.delenv(_OPENAI_KEY, raising=False)


# --------------------------------------------------------------------------
# validate_api_key
# --------------------------------------------------------------------------


def _response(status_code):
    resp = Mock()
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


def test_validate_accepts_a_200():
    with patch("gcode.setup.requests.get", return_value=_response(200)):
        valid, error = validate_api_key("sk-good")

    assert valid is True
    assert error == ""


def test_validate_sends_the_key_as_a_bearer_token():
    """The key has to reach the header, or a 200 proves nothing."""
    with patch("gcode.setup.requests.get", return_value=_response(200)) as get:
        validate_api_key("sk-good")

    headers = get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-good"
    assert get.call_args.kwargs["timeout"] == 15


def test_validate_reports_a_401_as_an_invalid_key():
    with patch("gcode.setup.requests.get", return_value=_response(401)):
        valid, error = validate_api_key("sk-bad")

    assert valid is False
    assert "Invalid API key" in error


def test_validate_reports_a_403_as_forbidden():
    """403 is a distinct case: the key parsed, the account is not allowed."""
    with patch("gcode.setup.requests.get", return_value=_response(403)):
        valid, error = validate_api_key("sk-forbidden")

    assert valid is False
    assert "forbidden" in error.lower()
    assert "Invalid API key" not in error


def test_401_and_403_do_not_share_a_message():
    with patch("gcode.setup.requests.get", return_value=_response(401)):
        _, unauthorised = validate_api_key("k")
    with patch("gcode.setup.requests.get", return_value=_response(403)):
        _, forbidden = validate_api_key("k")

    assert unauthorised != forbidden


@pytest.mark.parametrize(
    "exc",
    [
        requests.exceptions.ConnectionError("no route to host"),
        requests.exceptions.Timeout("timed out"),
        requests.exceptions.SSLError("bad handshake"),
    ],
)
def test_validate_reports_network_failures_without_raising(exc):
    """A user offline during setup must get a message, not a traceback."""
    with patch("gcode.setup.requests.get", side_effect=exc):
        valid, error = validate_api_key("sk-whatever")

    assert valid is False
    assert error


def test_validate_treats_an_unexpected_status_as_invalid():
    """raise_for_status covers the codes not handled explicitly."""
    resp = _response(500)
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")

    with patch("gcode.setup.requests.get", return_value=resp):
        valid, error = validate_api_key("sk-good")

    assert valid is False
    assert error


# --------------------------------------------------------------------------
# get_api_key
# --------------------------------------------------------------------------


def test_get_api_key_is_empty_when_nothing_is_set():
    assert get_api_key() == ""


def test_get_api_key_reads_openrouter(monkeypatch):
    monkeypatch.setenv(_OPENROUTER_KEY, "sk-router")

    assert get_api_key() == "sk-router"


def test_get_api_key_falls_back_to_openai(monkeypatch):
    monkeypatch.setenv(_OPENAI_KEY, "sk-openai")

    assert get_api_key() == "sk-openai"


def test_openrouter_wins_over_openai(monkeypatch):
    monkeypatch.setenv(_OPENROUTER_KEY, "sk-router")
    monkeypatch.setenv(_OPENAI_KEY, "sk-openai")

    assert get_api_key() == "sk-router"


def test_an_empty_openrouter_key_falls_through(monkeypatch):
    """`or` means a blank value is skipped rather than returned."""
    monkeypatch.setenv(_OPENROUTER_KEY, "")
    monkeypatch.setenv(_OPENAI_KEY, "sk-openai")

    assert get_api_key() == "sk-openai"


# --------------------------------------------------------------------------
# load_env
# --------------------------------------------------------------------------


def test_load_env_reads_the_file_when_present(env_file, monkeypatch):
    env_file.parent.mkdir(parents=True)
    env_file.write_text(f"{_OPENROUTER_KEY}=sk-from-file\n")

    load_env()

    assert get_api_key() == "sk-from-file"


def test_load_env_is_a_no_op_when_the_file_is_absent(env_file):
    """First run: no file yet, and this must not raise."""
    assert not env_file.exists()

    load_env()

    assert get_api_key() == ""


def test_load_env_overrides_an_existing_variable(env_file, monkeypatch):
    """override=True, so the file is the source of truth once it exists."""
    monkeypatch.setenv(_OPENROUTER_KEY, "sk-stale")
    env_file.parent.mkdir(parents=True)
    env_file.write_text(f"{_OPENROUTER_KEY}=sk-fresh\n")

    load_env()

    assert get_api_key() == "sk-fresh"


# --------------------------------------------------------------------------
# save_api_key
# --------------------------------------------------------------------------


def test_save_round_trips_through_the_environment(env_file):
    save_api_key("sk-saved")

    assert env_file.read_text().strip() == f"{_OPENAI_KEY}=sk-saved"
    assert get_api_key() == "sk-saved"


def test_save_creates_the_directory(env_file):
    """First run has no ~/.gcode at all."""
    assert not env_file.parent.exists()

    save_api_key("sk-saved")

    assert env_file.parent.is_dir()


def test_save_keeps_whichever_variable_was_already_set(env_file, monkeypatch):
    """A user on OPENROUTER_API_KEY should not silently switch variables."""
    monkeypatch.setenv(_OPENROUTER_KEY, "sk-old")

    save_api_key("sk-new")

    assert env_file.read_text().strip() == f"{_OPENROUTER_KEY}=sk-new"


def test_save_then_load_survives_a_restart(env_file, monkeypatch):
    """The point of persisting: a fresh process picks the key back up."""
    save_api_key("sk-persisted")
    monkeypatch.delenv(_OPENAI_KEY, raising=False)
    monkeypatch.delenv(_OPENROUTER_KEY, raising=False)
    assert get_api_key() == ""

    load_env()

    assert get_api_key() == "sk-persisted"
