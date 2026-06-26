"""In-memory registry of live sessions, indexed by 6-letter code."""

from __future__ import annotations

import secrets
import time

from .models import GameState, Session

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I/O to avoid confusion
CODE_LENGTH = 6

# Idle sessions are evicted to bound memory (no DB, everything is in RAM). Connected
# clients ping every ~15s, refreshing ``last_seen``, so only sessions abandoned by
# *every* client age out. A hard cap is a safety net against creation floods.
SESSION_TTL_MS = 6 * 60 * 60 * 1000  # 6h with no activity → evict
MAX_SESSIONS = 5000


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

    def _evict_idle(self) -> None:
        """Drop sessions with no activity for ``SESSION_TTL_MS``; if still over the
        hard cap, drop the least-recently-seen ones. Called on create so abandoned
        games don't accumulate forever."""
        cutoff = now_ms() - SESSION_TTL_MS
        for code in [c for c, s in self._sessions.items() if s.last_seen < cutoff]:
            del self._sessions[code]
        if len(self._sessions) >= MAX_SESSIONS:
            for code, _ in sorted(self._sessions.items(), key=lambda kv: kv[1].last_seen)[
                : len(self._sessions) - MAX_SESSIONS + 1
            ]:
                del self._sessions[code]

    def create(self) -> Session:
        self._evict_idle()
        now = now_ms()
        code = generate_code(set(self._sessions))
        session = Session(
            code=code,
            host_secret=secrets.token_urlsafe(24),
            created_at=now,
            last_seen=now,
            state=GameState.LOBBY,
        )
        self._sessions[code] = session
        return session

    def touch(self, session: Session) -> None:
        """Mark a session active so it isn't evicted (called on every WS message)."""
        session.last_seen = now_ms()

    def get(self, code: str) -> Session | None:
        return self._sessions.get(code.upper())

    def has_host_secret(self, secret: str) -> bool:
        """True if ``secret`` is the host_secret of some live session. Used to gate
        host-only HTTP endpoints (e.g. the Spotify token) to actual game hosts.
        Constant-time comparison so it doesn't leak secrets via timing."""
        if not secret:
            return False
        try:
            return any(secrets.compare_digest(secret, s.host_secret) for s in self._sessions.values())
        except TypeError:
            # compare_digest rejects non-ASCII str — treat as a non-match, not a 500.
            return False

    def remove(self, code: str) -> None:
        self._sessions.pop(code.upper(), None)

    def __contains__(self, code: str) -> bool:
        return code.upper() in self._sessions
