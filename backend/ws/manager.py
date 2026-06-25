"""WebSocket connection manager — turns engine :class:`Outbound` messages into
actual frames and routes them to the right connections of a session.

State lives in :class:`~game.store.SessionStore`; this layer only tracks live
sockets per session code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import WebSocket
from loguru import logger

from game.engine import Outbound
from game.models import Session
from game.store import now_ms


@dataclass
class Connection:
    ws: WebSocket
    role: str  # "host" | "player" | "tv"
    player_id: str | None = None


def envelope(type_: str, payload: dict) -> dict:
    """Standard server→client message (cahier §13). ``ts`` is always the
    server clock at emission."""
    return {"type": type_, "payload": payload, "ts": now_ms()}


@dataclass
class ConnectionManager:
    _conns: dict[str, list[Connection]] = field(default_factory=dict)

    def register(self, code: str, conn: Connection) -> None:
        self._conns.setdefault(code, []).append(conn)

    def unregister(self, code: str, conn: Connection) -> None:
        conns = self._conns.get(code)
        if not conns:
            return
        if conn in conns:
            conns.remove(conn)
        if not conns:
            self._conns.pop(code, None)

    def _targets(self, code: str, target: str) -> list[Connection]:
        conns = self._conns.get(code, [])
        if target == "all":
            return list(conns)
        if target == "host":
            return [c for c in conns if c.role == "host"]
        if target == "players":
            # The public round state (no answer) also feeds the shared TV screens.
            return [c for c in conns if c.role in ("player", "tv")]
        return [c for c in conns if c.player_id == target]  # unicast by player id

    async def _send(self, conn: Connection, type_: str, payload: dict) -> None:
        try:
            await conn.ws.send_json(envelope(type_, payload))
        except Exception as exc:  # socket may already be closing
            logger.debug("send failed ({}): {}", type_, exc)

    async def send(self, conn: Connection, type_: str, payload: dict) -> None:
        await self._send(conn, type_, payload)

    async def dispatch(self, session: Session, outbounds: list[Outbound]) -> None:
        for out in outbounds:
            for conn in self._targets(session.code, out.target):
                await self._send(conn, out.type, out.payload)

    async def disconnect_player(self, code: str, player_id: str | None) -> None:
        """Force-close every socket of a player (used after a kick)."""
        if not player_id:
            return
        for conn in [c for c in self._conns.get(code, []) if c.player_id == player_id]:
            try:
                await conn.ws.close(code=4000)
            except Exception:
                pass
            self.unregister(code, conn)
