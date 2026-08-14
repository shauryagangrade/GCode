"""Optional persistent configuration for GCode.

Reads ``.gcoderc`` (project root) then ``~/.gcode/config`` (user home) using a
simple ``key = value`` format with ``#`` comments. Settings are optional and
override built-in defaults, but command-line flags and environment variables
still take precedence:

    CLI flag / env var  >  config file  >  default

Supported keys: ``model``, ``auto_approve`` (true/false), ``system_prompt``,
and ``bash_timeout`` (seconds).
"""

from pathlib import Path
from typing import Any

CONFIG_FILE_NAME = ".gcoderc"
USER_CONFIG_PATH = Path.home() / ".gcode" / CONFIG_FILE_NAME

_BOOLS = {"true": True, "false": False, "yes": True, "no": False, "1": True, "0": False}


def _parse_value(raw: str) -> Any:
    """Parse a single config value into bool/int/string."""
    value = raw.strip()
    lowered = value.lower()
    if lowered in _BOOLS:
        return _BOOLS[lowered]
    try:
        return int(value)
    except ValueError:
        pass
    return value.strip("\"'")


def _load_file(path: Path) -> dict[str, Any]:
    """Parse a config file into a plain dict."""
    settings: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return settings
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            settings[key] = _parse_value(value)
    return settings


def load_config(project_root: str | None = None) -> dict[str, Any]:
    """Load merged config: project ``.gcoderc`` overrides user config.

    Later files win, so the project-local ``.gcoderc`` takes precedence over
    the user-level ``~/.gcode/.gcoderc``.
    """
    merged: dict[str, Any] = {}
    candidates = []
    if project_root:
        candidates.append(Path(project_root) / CONFIG_FILE_NAME)
    candidates.append(USER_CONFIG_PATH)
    for path in candidates:
        merged.update(_load_file(path))
    return merged


def resolve_model(
    config: dict[str, Any], cli_model: str | None, env_model: str | None
) -> str | None:
    """Resolve the model id: CLI > env > config > None."""
    return (
        cli_model
        or env_model
        or (config.get("model") if isinstance(config.get("model"), str) else None)
    )


def resolve_auto_approve(config: dict[str, Any], cli_flag: bool) -> bool:
    """Resolve auto-approve: CLI flag > config > False."""
    if cli_flag:
        return True
    value = config.get("auto_approve")
    return value is True


def resolve_bash_timeout(config: dict[str, Any], default: int) -> int:
    """Resolve the bash tool timeout in seconds (config > default)."""
    value = config.get("bash_timeout")
    if isinstance(value, int) and value > 0:
        return value
    return default


def resolve_system_prompt(config: dict[str, Any], default: str) -> str:
    """Resolve the system prompt (config > default)."""
    value = config.get("system_prompt")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default
