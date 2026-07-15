"""Parse provider/API errors into readable messages (no raw JSON)."""


import json


def _extract_error(obj):
    """Pull the inner error dict out of a body that may be ``{error: {...}}``."""
    if isinstance(obj, dict):
        inner = obj.get("error")
        if isinstance(inner, dict):
            return inner
    return obj


def _parse_body(body):
    if isinstance(body, dict):
        return _extract_error(body)
    if isinstance(body, str):
        try:
            return _extract_error(json.loads(body))
        except (ValueError, TypeError):
            return None
    return None


def format_model_error(exc) -> str:
    """Return a human-readable message for a model/API call failure.

    Prefers the structured error body (e.g. openai's ``APIStatusError.body``),
    falls back to parsing the exception text, then to the raw string. The
    provider's ``metadata.raw`` note (rate limits) and ``retry_after`` delay
    are surfaced when present.
    """
    info = _parse_body(getattr(exc, "body", None))
    if info is None:
        info = _parse_body(str(exc))

    if not isinstance(info, dict):
        return str(exc).strip()

    code = info.get("code")
    message = info.get("message") or info.get("error") or ""
    meta = info.get("metadata") or {}

    # For rate limits the provider's raw note is the most useful detail.
    if str(code) == "429" and meta.get("raw"):
        text = str(meta["raw"])
    else:
        text = str(message) if message else str(exc)

    retry = meta.get("retry_after_seconds") or meta.get("retry_after_seconds_raw")
    if retry:
        try:
            text = f"{text} Retry after ~{int(float(retry))}s."
        except (TypeError, ValueError):
            pass

    if code is not None:
        text = f"[{code}] {text}"
    return text.strip()
