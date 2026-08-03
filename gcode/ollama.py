"""Ollama integration for GCode: detect local Ollama server, list models, pull models.

Ollama runs a local inference server (default http://localhost:11434) with an
OpenAI-compatible API at /v1.  No API key is required.  This module provides
helpers to detect the server, list locally-installed models, and optionally
pull new ones.
"""

from typing import Dict, List, Optional, Tuple

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_V1_URL = f"{OLLAMA_BASE_URL}/v1"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"


def is_ollama_running() -> bool:
    """Return True if an Ollama server is reachable at the default address."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=3)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_local_models() -> Tuple[List[Dict], Optional[str]]:
    """Return a list of locally installed Ollama models.

    Each entry is a dict with keys ``name`` and ``size`` (in human form).
    Returns ``(models, error_or_None)``.
    """
    try:
        resp = requests.get(OLLAMA_TAGS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        return [], f"Could not reach Ollama server: {exc}"

    models = []
    for m in data.get("models", []):
        name = m.get("name", "")
        size_bytes = m.get("size", 0)
        models.append({
            "name": name,
            "size": _format_size(size_bytes),
        })
    models.sort(key=lambda x: x["name"])
    return models, None


def pull_model(model_name: str, ui=None) -> Tuple[bool, str]:
    """Pull a model from the Ollama registry.

    Streams progress to *ui* if provided. Returns ``(success, message)``.
    """
    try:
        payload = {"name": model_name, "stream": bool(ui)}
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json=payload,
            timeout=None,  # pulls can take a long time
        )
        resp.raise_for_status()
        return True, f"Successfully pulled {model_name}"
    except requests.exceptions.RequestException as exc:
        return False, f"Failed to pull {model_name}: {exc}"


def _format_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string (e.g. '7.4 GB')."""
    if size_bytes == 0:
        return "unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
