"""OpenRouter model catalog access and model-selection helpers for GCode.

There is no single catch-all "free" model id on OpenRouter; instead we fetch the
live catalog and let the user list/switch among every real `:free` model.
"""

import requests

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_MODEL = "qwen/qwen3-coder:free"


def list_free_models():
    """Return (sorted_list_of_free_model_ids, error_or_None).

    Best-effort: on a network failure the list is empty and ``error`` explains
    why, so callers can degrade gracefully.
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
        return [], f"Could not fetch model list: {exc}"

    ids = sorted(
        m["id"] for m in data.get("data", []) if m.get("id", "").endswith(":free")
    )
    return ids, None


def resolve_model_id(text, free_ids):
    """Resolve user input to a model id.

    Accepts a full model id, or a 1-based index into ``free_ids`` (as printed by
    ``/models``). Any id that looks like a model reference is also accepted even
    if it is not in the free list (e.g. a paid model).
    """
    text = (text or "").strip()
    if not text:
        return None, "No model specified."

    if text in free_ids:
        return text, None

    try:
        idx = int(text)
        if 1 <= idx <= len(free_ids):
            return free_ids[idx - 1], None
    except ValueError:
        pass

    if "/" in text or text.startswith("openrouter") or text.endswith(":free"):
        return text, None

    return None, f"Unknown model: {text}"
