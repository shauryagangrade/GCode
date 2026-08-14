"""Persistent chat history for GCode sessions.

Messages are serialized with LangChain's ``messages_to_dict`` /
``messages_from_dict`` so tool-call <-> tool-message pairing survives a reload.
"""

import contextlib
import json
import os
import sys
import tempfile

from langchain_core.messages import messages_from_dict, messages_to_dict

BASE_DIR = os.path.join(os.path.expanduser("~"), ".gcode")
DEFAULT_SESSION = "default"


def _path(session: str) -> str:
    os.makedirs(BASE_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session)
    return os.path.join(BASE_DIR, f"{safe}.json")


def load(session: str = DEFAULT_SESSION):
    """Load persisted messages for a session, or None if none exist.

    A missing file returns None silently. A file that exists but cannot be
    parsed is reported to stderr (naming the path) instead of being silently
    treated as "no history", so a corrupt session file cannot masquerade as an
    empty conversation.
    """
    path = _path(session)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return messages_from_dict(data)
    except Exception as exc:  # noqa: BLE001 — surface corrupt/malformed history
        print(
            f"Warning: could not read session history from {path} ({exc}). "
            "The file may be corrupt — inspect or remove it to start a fresh session.",
            file=sys.stderr,
        )
        return None


def save(session: str, messages) -> None:
    """Persist messages to disk atomically (includes the leading system message).

    Writes to a temporary file in the same directory and ``os.replace``s it
    into place, so an interrupted or failed save can never leave a partial
    session file behind. Failures are reported to stderr instead of being
    silently swallowed — a broken save should not look like "no history".
    """
    path = _path(session)
    try:
        data = json.dumps(messages_to_dict(messages), indent=2)
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp_path, path)
        except Exception:
            # Best-effort cleanup so a failed write leaves no stray temp file.
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
    except Exception as exc:  # noqa: BLE001 — persistence must never crash the REPL
        print(
            f"Warning: could not save session history to {path} ({exc}).",
            file=sys.stderr,
        )


def clear(session: str = DEFAULT_SESSION) -> None:
    path = _path(session)
    if os.path.isfile(path):
        os.remove(path)
