"""OpenRouter model catalog access and model-selection helpers for GCode.

There is no single catch-all "free" model id on OpenRouter; instead we fetch the
live catalog and let the user list/switch among every real `:free` model.

Also supports Ollama local models — see gcode.ollama.
"""

import requests

from gcode.errors import network_error_message, unknown_model_message
from gcode.ollama import is_ollama_running, list_local_models

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_MODEL = "qwen/qwen3-coder:free"


def list_free_models():
    """Return (list_of_free_model_entries, error_or_None).

    Best-effort: on a network failure the list is empty and ``error`` explains
    why, so callers can degrade gracefully.

    Each entry is a dict with ``id``, the OpenRouter ``context_length`` (token
    window) when known, and ``supports_tools`` derived from the catalog's
    ``supported_parameters`` (True when the model advertises ``tools``). Note
    ``supports_tools`` reflects the advertised capability, not a guarantee that
    the model works with GCode's tool schema.
    """
    try:
        resp = requests.get(
            OPENROUTER_MODELS_URL,
            timeout=20,
            headers={"User-Agent": "gcode/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:  # network / TLS / timeout
        return [], network_error_message("fetch the OpenRouter model list", exc)

    entries = []
    for m in data.get("data", []):
        if not m.get("id", "").endswith(":free"):
            continue
        supported = m.get("supported_parameters") or []
        entries.append(
            {
                "id": m["id"],
                "context_length": m.get("context_length") or 0,
                "supports_tools": "tools" in supported,
            }
        )
    entries.sort(key=lambda entry: entry["id"])
    return entries, None


def list_all_models():
    """Return a combined list of OpenRouter free models + local Ollama models.

    Each entry is a dict with keys ``id`` and ``source`` ("openrouter" or "ollama").
    Ollama models are prefixed with ``ollama/`` in the id. OpenRouter entries
    also carry ``context_length`` (token window) and ``supports_tools``; Ollama
    entries carry ``size`` where the local registry reports it.
    """
    all_models = []

    # OpenRouter free models
    free_entries, _err = list_free_models()
    for m in free_entries:
        all_models.append(
            {
                "id": m["id"],
                "source": "openrouter",
                "context_length": m.get("context_length") or 0,
                "supports_tools": m.get("supports_tools", False),
            }
        )

    # Ollama local models
    if is_ollama_running():
        ollama_models, _err = list_local_models()
        for m in ollama_models:
            name = m["name"]
            ollama_id = f"ollama/{name}"
            all_models.append(
                {
                    "id": ollama_id,
                    "source": "ollama",
                    "size": m.get("size", ""),
                }
            )

    return all_models


def resolve_model_id(text, all_models=None):
    """Resolve user input to a model id.

    Accepts a full model id, or a 1-based index into ``all_models`` (as printed by
    ``/models``). Any id that looks like a model reference is also accepted even
    if it is not in the model list (e.g. a paid model).

    For Ollama models, accepts both ``ollama/modelname`` and ``modelname``.
    """
    text = (text or "").strip()
    if not text:
        return None, "No model specified."

    model_ids = [m["id"] for m in all_models] if all_models else []

    # Direct match
    if text in model_ids:
        return text, None

    # Check if it's an Ollama model reference without prefix
    if not text.startswith("ollama/"):
        ollama_prefixed = f"ollama/{text}"
        if ollama_prefixed in model_ids:
            return ollama_prefixed, None

    # Index-based selection (1-based)
    try:
        idx = int(text)
        if 1 <= idx <= len(model_ids):
            return model_ids[idx - 1], None
    except ValueError:
        pass

    # Accept any valid-looking model reference
    if "/" in text or text.startswith("openrouter") or text.endswith(":free"):
        return text, None

    # Accept Ollama model references
    if text.startswith("ollama/"):
        return text, None

    return None, unknown_model_message(text)
