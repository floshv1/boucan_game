"""In-memory registry of live sessions, indexed by 6-letter code."""

from __future__ import annotations

import secrets
import time

from .models import GameState, Session

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I/O to avoid confusion
CODE_LENGTH = 6


def generate_code(existing: set[str]) -> str:
    """Return a fresh 6-letter uppercase code not present in ``existing``."""
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if code not in existing:
            return code


def now_ms() -> int:
    return int(time.time() * 1000)


class SessionStore:
    """Holds every active session in memory (cahier §15)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        code = generate_code(set(self._sessions))
        session = Session(
            code=code,
            host_secret=secrets.token_urlsafe(24),
            created_at=now_ms(),
            state=GameState.LOBBY,
        )
        self._sessions[code] = session
        return session

    def get(self, code: str) -> Session | None:
        return self._sessions.get(code.upper())

    def remove(self, code: str) -> None:
        self._sessions.pop(code.upper(), None)

    def __contains__(self, code: str) -> bool:
        return code.upper() in self._sessions
