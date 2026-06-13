from collections import deque
from app.utils.logger import get_logger

log = get_logger(__name__)

_sessions: dict[str, deque] = {}
MAX_TURNS = 5


def get_history(session_id: str) -> list:
    if session_id not in _sessions:
        return []
    return list(_sessions[session_id])


def add_turn(session_id: str, question: str, answer: str):
    if session_id not in _sessions:
        _sessions[session_id] = deque(maxlen=MAX_TURNS * 2)
    _sessions[session_id].append({"role": "user",      "content": question})
    _sessions[session_id].append({"role": "assistant",  "content": answer})
    log.debug(f"event=turn_added session_id={session_id[:8]} turns={len(_sessions[session_id])//2}")


def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
        log.info(f"event=session_cleared session_id={session_id[:8]}")