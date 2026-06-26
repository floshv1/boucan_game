"""Boucan backend — FastAPI app, WebSocket endpoint, in-memory game state.

Phase 1 implements session management + buzzer mode. No database: sessions,
players and scores live in RAM and reset on restart (cahier §15).
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from game import blindtest, engine, packs_store, qcm
from game.models import GameMode, GameState
from game.store import SessionStore, now_ms
from routers.packs import router as packs_router
from routers.sessions import router as sessions_router
from routers.spotify import router as spotify_router
from ws.manager import Connection, ConnectionManager, envelope

# --------------------------------------------------------------------------- #
# Config & logging
# --------------------------------------------------------------------------- #
load_dotenv()

PORT_BACKEND = int(os.environ.get("PORT_BACKEND", "8200"))
# CORS defaults to the frontend origin: the app only ever talks to the backend
# same-origin (via the Next proxy) or over the WebSocket (not CORS-governed), so a
# wildcard is unnecessary and would let any site read responses (e.g. the Spotify
# token). Override with CORS_ORIGINS (comma-separated) if you really need to.
_FRONTEND_ORIGIN = os.environ.get("FRONTEND_URL", "http://localhost:3200").rstrip("/")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", _FRONTEND_ORIGIN).split(",") if o.strip()] or [
    _FRONTEND_ORIGIN
]


class _InterceptHandler(logging.Handler):
    """Route stdlib logging (uvicorn) through loguru, matching the repo style."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)

# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
app = FastAPI(title="Boucan API", redirect_slashes=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.store = SessionStore()

manager = ConnectionManager()

# Origins explicitly allowed to open the WebSocket. A wildcard CORS setting also
# opens the WS to any site (matching the CORS posture).
_WS_ALLOW_ANY = "*" in CORS_ORIGINS
_WS_ALLOWED_HOSTS = {h for h in (urlparse(o).hostname for o in CORS_ORIGINS) if h}


def _ws_origin_allowed(ws: WebSocket) -> bool:
    """Reject cross-site WebSocket handshakes (CSWSH). Browsers always send Origin;
    non-browser clients omit it (allowed). An Origin is accepted when its host is the
    same as the host the backend was reached on — which the app always satisfies, since
    the page and the WS share a hostname (e.g. frontend :3200 → backend :8200 on the
    same Tailscale host / LAN IP) — or when it's in the configured CORS origins."""
    if _WS_ALLOW_ANY:
        return True
    origin = ws.headers.get("origin")
    if not origin:  # native clients / same-origin requests
        return True
    origin_host = urlparse(origin).hostname
    if not origin_host:
        return False
    backend_host = (ws.headers.get("host", "").rsplit(":", 1)[0]) or None
    return origin_host == backend_host or origin_host in _WS_ALLOWED_HOSTS

_qcm_timers: dict[str, asyncio.Task] = {}
# Actions only the QCM flow defines (no buzzer equivalent) — always route to qcm.
QCM_ONLY_ACTIONS = {"set_qcm_rounds", "start_qcm"}
# Actions whose names are shared with the buzzer flow — route by session mode.
QCM_SHARED_ACTIONS = {"reveal", "skip", "next", "replay_game"}
# Actions only the blindtest flow defines.
BLINDTEST_ONLY_ACTIONS = {
    "set_blindtest_tracks",
    "start_blindtest",
    "validate_bt",
    "continue_bt",
    "replay_bt",
    "pause_bt",
    "resume_bt",
    "bt_started",
}
# Names shared between blindtest and buzzer/qcm — disambiguated by mode.
BLINDTEST_SHARED_ACTIONS = {"reveal", "skip", "next", "invalidate", "replay_game"}


def _cancel_timer(code: str) -> None:
    task = _qcm_timers.pop(code, None)
    if task is not None and not task.done():
        task.cancel()


async def _sync_qcm_timer(session) -> None:
    """Keep exactly one auto-reveal timer alive while a question is active."""
    code = session.code
    _cancel_timer(code)
    if session.state is GameState.QUESTION_ACTIVE:
        delay = max(0.0, (session.question_ends_at - now_ms()) / 1000.0)
        _qcm_timers[code] = asyncio.create_task(_auto_reveal(session, delay))


async def _auto_reveal(session, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
        if session.state is GameState.QUESTION_ACTIVE:
            await manager.dispatch(session, qcm.reveal(session))
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # never let a background task die with an unretrieved error
        logger.warning("auto-reveal timer failed: {}", exc)


async def _sync_blindtest_timer(session) -> None:
    """Keep exactly one auto-pause timer alive while a blindtest track is playing under a cap."""
    code = session.code
    _cancel_timer(code)
    if session.state is GameState.BUZZER_OPEN and session.bt_play_ends_at > 0:
        delay = max(0.0, (session.bt_play_ends_at - now_ms()) / 1000.0)
        _qcm_timers[code] = asyncio.create_task(_auto_pause_blindtest(session, delay))


async def _auto_pause_blindtest(session, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
        if session.state is GameState.BUZZER_OPEN and not session.revealed:
            await manager.dispatch(session, blindtest.on_play_timeout(session))
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # never let a background task die with an unretrieved error
        logger.warning("blindtest auto-pause timer failed: {}", exc)


async def _sync_buzzer_timer(session) -> None:
    """Keep exactly one auto-reveal timer alive while a buzzer round is open with a
    countdown and nobody has buzzed. Reschedules against the absolute deadline, so
    re-syncing mid-round (e.g. after an unrelated host action) keeps the same end."""
    code = session.code
    _cancel_timer(code)
    if (
        session.mode is GameMode.BUZZER
        and session.state is GameState.BUZZER_OPEN
        and not session.revealed
        and session.buzz_ends_at > 0
    ):
        delay = max(0.0, (session.buzz_ends_at - now_ms()) / 1000.0)
        _qcm_timers[code] = asyncio.create_task(_auto_reveal_buzzer(session, delay))


async def _auto_reveal_buzzer(session, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
        if session.state is GameState.BUZZER_OPEN and not session.revealed and session.floor_player_id is None:
            await manager.dispatch(session, engine.reveal(session))
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # never let a background task die with an unretrieved error
        logger.warning("buzzer auto-reveal timer failed: {}", exc)


async def _broadcast_state_sync(session) -> None:
    """Push a fresh, role-filtered ``state_sync`` to every live connection of a
    session. Used after a mode-agnostic transition (e.g. return_to_lobby) where
    there is no incremental message that moves all roles at once."""
    for conn in list(manager._conns.get(session.code, [])):
        if conn.role == "tv":
            snap = engine.state_sync_outbound(session, role="tv")
            snap.payload["qcm"] = qcm.state_sync_payload(session, role="tv")
            snap.payload["blindtest"] = blindtest.state_sync_payload(session, role="tv")
        elif conn.role == "player":
            snap = engine.state_sync_outbound(session, role="player", player_id=conn.player_id)
            snap.payload["qcm"] = qcm.state_sync_payload(session, role="player", player_id=conn.player_id)
            snap.payload["blindtest"] = blindtest.state_sync_payload(session, role="player", player_id=conn.player_id)
        else:
            snap = engine.state_sync_outbound(session, role="host")
            snap.payload["qcm"] = qcm.state_sync_payload(session, role="host")
            snap.payload["blindtest"] = blindtest.state_sync_payload(session, role="host")
        await manager.send(conn, snap.type, snap.payload)


app.include_router(sessions_router, prefix="/api")
app.include_router(packs_router, prefix="/api")
app.include_router(spotify_router)

# Serve uploaded question images. _media_dir() creates the dir if missing.
app.mount("/media", StaticFiles(directory=packs_store._media_dir()), name="media")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
async def _handle_message(session, conn: Connection, msg: dict) -> None:
    mtype = msg.get("type")
    payload = msg.get("payload") or {}
    session.last_seen = now_ms()  # keep active sessions from being evicted (store TTL)

    if mtype == "ping":
        await manager.send(conn, "pong", {})
        return

    if mtype == "buzz":
        if conn.role == "player" and conn.player_id:
            if session.mode is GameMode.BLINDTEST:
                await manager.dispatch(session, blindtest.on_buzz(session, conn.player_id, now_ms()))
                await _sync_blindtest_timer(session)
            elif now_ms() >= session.buzz_open_at:  # locked during the reading window
                await manager.dispatch(session, engine.buzz(session, conn.player_id, now_ms()))
                await _sync_buzzer_timer(session)  # a buzz pauses the countdown (→ BUZZED)
            else:
                logger.debug("[{}] buzz dropped: reading window ({}ms left)", session.code, session.buzz_open_at - now_ms())
        return

    if mtype == "answer_submit":
        if conn.role == "player" and conn.player_id:
            # Choices are locked during the reading window (cahier: temps de lecture).
            if now_ms() >= session.question_started_at + engine.READING_MS:
                await manager.dispatch(
                    session, qcm.answer_submit(session, conn.player_id, payload.get("choice", -1), now_ms())
                )
                if qcm.all_answered(session):
                    await manager.dispatch(session, qcm.reveal(session))
            await _sync_qcm_timer(session)
        return

    if mtype == "host_action":
        if conn.role != "host":
            await manager.send(conn, "error", {"code": "forbidden", "message": "Action réservée à l'hôte."})
            return
        action = payload.get("action", "")
        logger.info("[{}] host_action: {}", session.code, action)
        # Mode-agnostic: rewind a finished game to the lobby (same code, players
        # kept) and re-sync everyone to the preparation screen.
        if action == "return_to_lobby":
            if engine.return_to_lobby(session):
                _cancel_timer(session.code)
                await _broadcast_state_sync(session)
            return
        # "reveal"/"skip"/"next" exist in both flows — disambiguate by mode so the
        # buzzer's reveal/next still reach engine.handle_host_action (cahier §12).
        is_qcm = action in QCM_ONLY_ACTIONS or (action in QCM_SHARED_ACTIONS and session.mode is GameMode.QCM)
        is_blindtest = action in BLINDTEST_ONLY_ACTIONS or (
            action in BLINDTEST_SHARED_ACTIONS and session.mode is GameMode.BLINDTEST
        )
        if is_qcm:
            await manager.dispatch(session, _run_qcm_host_action(session, action, payload))
            await _sync_qcm_timer(session)
            return
        elif is_blindtest:
            await manager.dispatch(session, _run_blindtest_host_action(session, action, payload))
            await _sync_blindtest_timer(session)
            return
        await manager.dispatch(session, engine.handle_host_action(session, action, payload))
        await _sync_buzzer_timer(session)  # (re)opening the buzzer arms the auto-reveal countdown
        if action == "kick":
            await manager.disconnect_player(session.code, payload.get("player_id"))
        return

    logger.debug("ignored ws message type={} state={}", mtype, session.state)


def _run_qcm_host_action(session, action: str, payload: dict) -> list:
    match action:
        case "set_qcm_rounds":
            items = payload.get("rounds")
            if not isinstance(items, list):
                return []
            return qcm.set_qcm_rounds(
                session,
                items,
                shuffle_questions=bool(payload.get("shuffle_questions")),
                shuffle_choices=bool(payload.get("shuffle_choices")),
            )
        case "start_qcm":
            return qcm.start_qcm(session, now_ms())
        case "reveal":
            return qcm.reveal(session)
        case "skip":
            return qcm.reveal(session, award=False)
        case "next":
            if session.state is GameState.REVEAL:
                return qcm.to_scoreboard(session)
            if session.state is GameState.SCOREBOARD:
                return qcm.next_(session, now_ms())
            return []
        case "replay_game":
            return qcm.replay_game(session, now_ms())
        case _:
            return []


def _run_blindtest_host_action(session, action: str, payload: dict) -> list:
    match action:
        case "set_blindtest_tracks":
            tracks = payload.get("tracks")
            if not isinstance(tracks, list):
                return []
            kwargs: dict = {}
            if "max_play_s" in payload:
                kwargs["max_play_s"] = int(payload["max_play_s"])
            if "random_start" in payload:
                kwargs["random_start"] = bool(payload["random_start"])
            if "countdown" in payload:
                kwargs["countdown"] = bool(payload["countdown"])
            if "points_title" in payload:
                kwargs["points_title"] = int(payload["points_title"])
            if "points_artist" in payload:
                kwargs["points_artist"] = int(payload["points_artist"])
            return blindtest.set_blindtest_tracks(session, tracks, **kwargs)
        case "start_blindtest":
            return blindtest.start_blindtest(session, now_ms())
        case "validate_bt":
            return blindtest.validate(
                session,
                title=bool(payload.get("title")),
                artist=bool(payload.get("artist")),
                now=now_ms(),
            )
        case "continue_bt":
            return blindtest.cont(session, now_ms())
        case "replay_bt":
            return blindtest.replay(session, now_ms())
        case "pause_bt":
            return blindtest.pause_bt(session, now_ms())
        case "resume_bt":
            return blindtest.resume_bt(session, now_ms())
        case "bt_started":
            return blindtest.mark_started(session, now_ms())
        case "reveal" | "skip":
            return blindtest.reveal(session, now_ms())
        case "invalidate":
            return blindtest.invalidate(session, now_ms())
        case "next":
            if session.state is GameState.REVEAL:
                return blindtest.to_scoreboard(session, now_ms())
            if session.state is GameState.SCOREBOARD:
                return blindtest.next_(session, now_ms())
            return []
        case "replay_game":
            return blindtest.replay_game(session, now_ms())
        case _:
            return []


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    if not _ws_origin_allowed(ws):
        logger.warning("ws rejected: cross-site origin {!r}", ws.headers.get("origin"))
        await ws.close(code=1008)  # policy violation
        return
    store: SessionStore = ws.app.state.store
    conn: Connection | None = None
    code: str | None = None
    session = None

    try:
        first = await ws.receive_json()
        if first.get("type") != "join":
            await ws.send_json(envelope("error", {"code": "expected_join", "message": "Premier message: join."}))
            await ws.close()
            return

        payload = first.get("payload") or {}
        code = (payload.get("code") or "").upper()
        session = store.get(code)
        if session is None:
            await ws.send_json(envelope("error", {"code": "no_session", "message": "Session introuvable."}))
            await ws.close()
            return

        role = payload.get("role", "player")
        if role == "host":
            if not secrets.compare_digest(str(payload.get("host_secret") or ""), session.host_secret):
                await ws.send_json(envelope("error", {"code": "bad_secret", "message": "Secret hôte invalide."}))
                await ws.close()
                return
            conn = Connection(ws=ws, role="host", player_id=None)
            manager.register(code, conn)
            snapshot = engine.state_sync_outbound(session, role="host")
            snapshot.payload["qcm"] = qcm.state_sync_payload(session, role="host")
            snapshot.payload["blindtest"] = blindtest.state_sync_payload(session, role="host")
            await manager.send(conn, snapshot.type, snapshot.payload)
        elif role == "tv":
            # Public shared screen: no secret, no pseudo, no Player created. It
            # only ever receives the answer-free public payloads (cahier §16).
            conn = Connection(ws=ws, role="tv", player_id=None)
            manager.register(code, conn)
            snapshot = engine.state_sync_outbound(session, role="tv")
            snapshot.payload["qcm"] = qcm.state_sync_payload(session, role="tv")
            snapshot.payload["blindtest"] = blindtest.state_sync_payload(session, role="tv")
            await manager.send(conn, snapshot.type, snapshot.payload)
        else:
            player, outs = engine.join(session, payload.get("pseudo", ""), payload.get("reconnect_token"))
            for o in outs:
                if o.type == "state_sync":
                    o.payload["qcm"] = qcm.state_sync_payload(session, role="player", player_id=player.id)
                    o.payload["blindtest"] = blindtest.state_sync_payload(session, role="player", player_id=player.id)
            conn = Connection(ws=ws, role="player", player_id=player.id)
            manager.register(code, conn)
            await manager.dispatch(session, outs)

        while True:
            msg = await ws.receive_json()
            await _handle_message(session, conn, msg)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws error: {}", exc)
    finally:
        if conn is not None and code is not None:
            manager.unregister(code, conn)
            if session is not None and conn.role == "player" and conn.player_id:
                await manager.dispatch(session, engine.on_disconnect(session, conn.player_id))
                # A floor-holder leaving can reopen the buzzer → (re)arm its countdown.
                await _sync_buzzer_timer(session)
            if not manager._conns.get(code):
                _cancel_timer(code)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT_BACKEND, reload=True)
