MAX_HISTORY_MESSAGES = 40

_HISTORY: dict[str, list] = {}


def get_history(session_id: str) -> list:
    return _HISTORY.setdefault(session_id, [])


def save_history(session_id: str, history: list) -> None:
    _HISTORY[session_id] = history[-MAX_HISTORY_MESSAGES:]
