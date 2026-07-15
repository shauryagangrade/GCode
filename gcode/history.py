"""Persistent chat history for GCode sessions.

Messages are serialized with LangChain's ``messages_to_dict`` /
``messages_from_dict`` so tool-call <-> tool-message pairing survives a reload.
"""

import json
import os

from langchain_core.messages import messages_from_dict, messages_to_dict

BASE_DIR = os.path.join(os.path.expanduser("~"), ".gcode")
DEFAULT_SESSION = "default"


def _path(session: str) -> str:
    os.makedirs(BASE_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session)
    return os.path.join(BASE_DIR, f"{safe}.json")


def load(session: str = DEFAULT_SESSION):
    """Load persisted messages for a session, or None if none exist."""
    path = _path(session)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return messages_from_dict(data)
    except Exception:
        return None


def save(session: str, messages) -> None:
    """Persist messages to disk (includes the leading system message)."""
    path = _path(session)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(messages_to_dict(messages), f, indent=2)
    except Exception:
        pass


def clear(session: str = DEFAULT_SESSION) -> None:
    path = _path(session)
    if os.path.isfile(path):
        os.remove(path)
