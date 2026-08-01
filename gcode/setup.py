"""API key setup and validation for GCode.

Handles first-run setup: checks for an existing key, prompts the user,
validates against OpenRouter, and persists to ``~/.gcode/.env``.
"""

import os
from pathlib import Path

import questionary
import requests
from dotenv import load_dotenv

# Where we store the user's API key
_ENV_DIR = Path.home() / ".gcode"
_ENV_FILE = _ENV_DIR / ".env"

_OPENROUTER_KEY = "OPENROUTER_API_KEY"
_OPENAI_KEY = "OPENAI_API_KEY"


def get_api_key() -> str:
    """Return the currently configured API key (or empty string).

    Checks ``OPENROUTER_API_KEY`` first, then ``OPENAI_API_KEY``.
    """
    return os.environ.get(_OPENROUTER_KEY) or os.environ.get(_OPENAI_KEY, "")


def load_env() -> None:
    """Load ``~/.gcode/.env`` into the process environment."""
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=True)


def validate_api_key(key: str) -> tuple[bool, str]:
    """Validate *key* by hitting the OpenRouter models endpoint.

    Returns ``(is_valid, error_or_empty)``.
    """
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            timeout=15,
            headers={"Authorization": f"Bearer {key}", "User-Agent": "gcode/0.1"},
        )
        if resp.status_code == 401:
            return False, "Invalid API key (authentication failed)."
        if resp.status_code == 403:
            return False, "API key was rejected (forbidden)."
        resp.raise_for_status()
        return True, ""
    except requests.exceptions.RequestException as exc:
        return False, f"Network error while validating key: {exc}"


def prompt_for_api_key() -> str:
    """Interactively ask the user for an OpenRouter API key.

    Returns the key string, or ``""`` if the user cancelled.
    """
    print()
    print("  GCode needs an OpenRouter API key to talk to AI models.")
    print("  Get a free key at: https://openrouter.ai/keys")
    print()

    key = questionary.text(
        "Paste your OpenRouter API key:",
        validate=lambda t: True if t.strip() else "Key cannot be empty.",
    ).ask()

    return (key or "").strip()


def save_api_key(key: str) -> None:
    """Persist *key* to ``~/.gcode/.env`` and reload the environment.

    Preserves whichever env var (``OPENROUTER_API_KEY`` or
    ``OPENAI_API_KEY``) was already set.
    """
    var_name = _OPENROUTER_KEY if os.environ.get(_OPENROUTER_KEY) else _OPENAI_KEY
    _ENV_DIR.mkdir(parents=True, exist_ok=True)
    _ENV_FILE.write_text(f"{var_name}={key}\n")
    load_dotenv(_ENV_FILE, override=True)


def setup_flow(force: bool = False) -> str:
    """Run the full interactive setup flow.

    When *force* is ``False`` (the default), an existing key is returned
    immediately.  When ``True``, the user is always prompted for a new key.

    Returns the API key, or ``""`` if the user cancelled or validation failed.
    """
    load_env()
    if not force:
        existing = get_api_key()
        if existing:
            return existing

    while True:
        key = prompt_for_api_key()
        if not key:
            return ""

        valid, err = validate_api_key(key)
        if valid:
            save_api_key(key)
            print()
            print("  ✓ API key saved to", _ENV_FILE)
            print()
            return key

        print(f"\n  ✗ {err}\n")
        retry = questionary.confirm("Try again?").ask()
        if not retry:
            return ""
