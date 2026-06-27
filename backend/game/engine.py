"""Pure game logic for Phase 1 (buzzer mode).

The engine never touches the network. Each function mutates a :class:`Session`
and returns a list of :class:`Outbound` messages describing *what* to send and
*to whom* — the WebSocket layer (``ws/manager.py``) turns those into actual
frames. Keeping this layer pure makes the buzzer arbitration (cahier §14)
straightforward to unit-test.

Targets used by :class:`Outbound`:
  * ``"all"``     — every connection in the session (host + players)
  * ``"host"``    — the host connection only
  * ``"players"`` — every player, but not the host
  * ``<player_id>`` — a single player (unicast)
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import uuid4

from loguru import logger

from .models import BuzzEntry, GameMode, GameState, Player, PreparedRound, Session
from .store import now_ms

# Reading window before a buzzer round opens or QCM choices appear, so players can
# read the question (or listen) first. Shared with qcm.py.
READING_MS = 3000


@dataclass
class Outbound:
    target: str
    type: str
    payload: dict


# --------------------------------------------------------------------------- #
# Payload builders
# --------------------------------------------------------------------------- #
def _ranked(session: Session) -> tuple[list[Player], dict[str, int]]:
    ordered = sorted(session.players.values(), key=lambda p: (-p.score, p.pseudo.lower()))
    ranks: dict[str, int] = {}
    last_score: int | None = None
    last_rank = 0
    for i, player in enumerate(ordered, start=1):
        if player.score != last_score:  # ties share a rank (cahier §19)
            last_rank = i
            last_score = player.score
        ranks[player.id] = last_rank
    return ordered, ranks


def player_list_payload(session: Session) -> dict:
    ordered, ranks = _ranked(session)
    return {
        "players": [
            {
                "id": p.id,
                "pseudo": p.pseudo,
                "score": p.score,
                "connected": p.connected,
                "rank": ranks[p.id],
            }
            for p in ordered
        ]
    }


def _pseudo(session: Session, player_id: str) -> str:
    player = session.players.get(player_id)
    return player.pseudo if player else "—"


def buzz_payload(session: Session) -> dict:
    return {
        "state": session.state.value,
        "floor_player_id": session.floor_player_id,
        # Post-buzz answer countdown: clients show a depleting bar for the
        # floor-holder; server auto-invalidates at answer_ends_at (0 = no limit).
        "answer_ends_at": session.answer_ends_at,
        "server_now": now_ms(),
        # Players barred from (re)buzzing this round (wrong answer / already scored).
        # Non-secret: lets clients gray out the buzzer instead of letting a barred
        # player press it only for the server to reject the buzz.
        "excluded_ids": list(session.excluded_ids),
        "queue": [
            {
                "player_id": e.player_id,
                "pseudo": _pseudo(session, e.player_id),
                "order": e.order,
                "delta_ms": e.delta_ms,
            }
            for e in session.buzz_queue
        ],
    }


def round_state_payload(session: Session, *, include_answer: bool) -> dict:
    show_answer = include_answer or session.revealed
    return {
        "state": session.state.value,
        "question_text": session.question_text,
        "points": session.points,
        "bonus": session.bonus,
        "image": session.image,
        "revealed": session.revealed,
        "floor_player_id": session.floor_player_id,
        "round_index": session.round_index,
        "round_total": len(session.rounds),
        "answer": session.answer if show_answer else None,
        # Reading window: clients keep the buzzer locked + show "Lecture…" until
        # buzz_open_at; server_now lets them correct for clock skew (see blindtest).
        "buzz_open_at": session.buzz_open_at,
        # Buzzer countdown: server auto-reveals at buzz_ends_at if nobody buzzes
        # (0 = no limit). Clients show a depleting bar between buzz_open_at and here.
        "buzz_ends_at": session.buzz_ends_at,
        "server_now": now_ms(),
    }


def _round_state_outbounds(session: Session) -> list[Outbound]:
    """Role-filtered round state: the host sees the answer, players never do
    before REVEAL (cahier §16)."""
    return [
        Outbound("host", "round_state", round_state_payload(session, include_answer=True)),
        Outbound("players", "round_state", round_state_payload(session, include_answer=False)),
    ]


def _buzz_outbound(session: Session) -> Outbound:
    return Outbound("all", "buzz_locked", buzz_payload(session))


def _player_list_outbound(session: Session) -> Outbound:
    return Outbound("all", "player_list", player_list_payload(session))


def state_sync_outbound(session: Session, *, role: str, player_id: str | None = None) -> Outbound:
    """Full snapshot sent to a single recipient on (re)connection (cahier §13)."""
    target = player_id if role == "player" and player_id else "host"
    you: dict = {"role": role, "id": player_id}
    if role == "player" and player_id and player_id in session.players:
        you["reconnect_token"] = session.players[player_id].reconnect_token
    payload = {
        "code": session.code,
        "you": you,
        "round": round_state_payload(session, include_answer=(role == "host")),
        "player_list": player_list_payload(session),
        "buzz": buzz_payload(session),
        "stats": stats_payload(session),
    }
    return Outbound(target, "state_sync", payload)


# --------------------------------------------------------------------------- #
# Players joining / leaving
# --------------------------------------------------------------------------- #
def _find_by_token(session: Session, token: str | None) -> Player | None:
    if not token:
        return None
    for player in session.players.values():
        if player.reconnect_token == token:
            return player
    return None


def _unique_pseudo(session: Session, pseudo: str) -> str:
    existing = {p.pseudo for p in session.players.values()}
    if pseudo not in existing:
        return pseudo
    n = 2
    while f"{pseudo} ({n})" in existing:
        n += 1
    return f"{pseudo} ({n})"


def join(session: Session, pseudo: str, reconnect_token: str | None = None) -> tuple[Player, list[Outbound]]:
    """Attach a player. With a valid ``reconnect_token`` the existing player is
    reattached (score + place kept); otherwise a new player is created with a
    de-duplicated pseudo."""
    existing = _find_by_token(session, reconnect_token)
    if existing is not None:
        existing.connected = True
        outs = [
            state_sync_outbound(session, role="player", player_id=existing.id),
            _player_list_outbound(session),
        ]
        return existing, outs

    player = Player(
        id=uuid4().hex,
        pseudo=_unique_pseudo(session, (pseudo or "Joueur").strip()[:24] or "Joueur"),
        reconnect_token=secrets.token_urlsafe(24),
    )
    session.players[player.id] = player
    outs = [
        state_sync_outbound(session, role="player", player_id=player.id),
        _player_list_outbound(session),
    ]
    return player, outs


def _advance_floor_if_departed(session: Session, player_id: str, now: int | None = None) -> list[Outbound]:
    """If ``player_id`` held the floor, pass it to the next in the queue, or
    reopen the buzzer if the queue is exhausted (cahier §14/§19)."""
    if session.state is not GameState.BUZZED or session.floor_player_id != player_id:
        return []
    session.floor_index += 1
    if session.floor_index >= len(session.buzz_queue):
        session.state = GameState.BUZZER_OPEN
        session.floor_index = 0
        # Buzzer mode: the floor-holder left, so restart the countdown for the
        # reopened (empty) buzzer — otherwise the stale deadline would fire instantly.
        if session.mode is GameMode.BUZZER:
            if now is None:
                now = now_ms()
            session.buzz_open_at = now
            session.buzz_ends_at = now + session.buzz_limit_ms if session.buzz_limit_ms > 0 else 0
    return [*_round_state_outbounds(session), _buzz_outbound(session)]


def on_disconnect(session: Session, player_id: str) -> list[Outbound]:
    """Mark a player disconnected (kept for reconnection) and free the floor if
    they held it."""
    player = session.players.get(player_id)
    if player is None:
        return []
    player.connected = False
    outs = _advance_floor_if_departed(session, player_id)
    outs.append(_player_list_outbound(session))
    return outs


# --------------------------------------------------------------------------- #
# Buzzer arbitration (cahier §14)
# --------------------------------------------------------------------------- #
def buzz(session: Session, player_id: str, now: int) -> list[Outbound]:
    if session.state not in (GameState.BUZZER_OPEN, GameState.BUZZED):
        return []
    if session.revealed or player_id not in session.players:
        return []
    if player_id in session.buzzed_ids:  # idempotent: one buzz per round
        return []
    if player_id in session.excluded_ids:  # barred this round (wrong answer / already scored)
        return []

    first_ts = session.buzz_queue[0].ts if session.buzz_queue else now
    session.buzz_queue.append(
        BuzzEntry(
            player_id=player_id,
            ts=now,
            order=len(session.buzz_queue) + 1,
            delta_ms=now - first_ts,
        )
    )
    session.buzzed_ids.add(player_id)
    if session.state is GameState.BUZZER_OPEN:
        session.state = GameState.BUZZED
        session.floor_index = 0
        # Arm the per-buzz answer window: if the floor-holder doesn't get judged in
        # time, main.py auto-invalidates (counts as a wrong answer).
        session.answer_ends_at = now + session.buzz_answer_ms if session.buzz_answer_ms > 0 else 0
    return [*_round_state_outbounds(session), _buzz_outbound(session)]


# --------------------------------------------------------------------------- #
# Host actions
# --------------------------------------------------------------------------- #
def _reset_round_fields(session: Session) -> None:
    session.revealed = False
    session.buzz_queue = []
    session.buzzed_ids = set()
    session.excluded_ids = set()  # new round: everyone may buzz again
    session.floor_index = 0
    session.buzz_ends_at = 0  # cleared here; (re)open paths set it after this
    session.answer_ends_at = 0


def _open_round(
    session: Session,
    question_text: str | None,
    answer: str | None,
    points: int | None,
    now: int,
    image: str | None = None,
    bonus: bool = False,
) -> list[Outbound]:
    """Open the buzzer for a round from *any* state (used by both the manual
    ``open_buzzer`` and the prepared-list ``load_round``). A round that carries a
    question text gets a reading window (buzzer locked for READING_MS); an ad-hoc
    "buzzer immédiat" with no text opens straight away."""
    session.state = GameState.BUZZER_OPEN
    session.question_text = question_text or None
    session.answer = answer or None
    session.points = points if points is not None else 1
    session.bonus = bonus
    session.image = image or None
    session.buzz_open_at = now + READING_MS if session.question_text else now
    _reset_round_fields(session)
    session.buzz_ends_at = session.buzz_open_at + session.buzz_limit_ms if session.buzz_limit_ms > 0 else 0
    logger.info(
        "[{}] buzzer round opened (q={!r}, reading={}ms, limit={}ms)",
        session.code,
        (session.question_text or "")[:40],
        session.buzz_open_at - now,
        session.buzz_limit_ms,
    )
    return [*_round_state_outbounds(session), _buzz_outbound(session)]


def open_buzzer(
    session: Session,
    now: int | None = None,
    question_text: str | None = None,
    answer: str | None = None,
    points: int | None = None,
    image: str | None = None,
    bonus: bool = False,
) -> list[Outbound]:
    """Manual ad-hoc round (LOBBY only) — kept for improvised / blindtest rounds
    where the host opens a buzzer without a prepared list."""
    if session.state is not GameState.LOBBY:
        return []
    if now is None:
        now = now_ms()
    return _open_round(session, question_text, answer, points, now, image, bonus)


# --------------------------------------------------------------------------- #
# Prepared round list (itération 2)
# --------------------------------------------------------------------------- #
def _prepared_rounds_outbound(session: Session) -> Outbound:
    """Full list *with answers* — host only, never sent to players/TV."""
    return Outbound(
        "host",
        "prepared_rounds",
        {
            "index": session.round_index,
            "rounds": [
                {
                    "question_text": r.question_text,
                    "answer": r.answer,
                    "points": r.points,
                    "bonus": r.bonus,
                    "image": r.image,
                }
                for r in session.rounds
            ],
        },
    )


def set_rounds(
    session: Session,
    items: list[dict],
    buzz_limit_s: int | None = None,
    buzz_answer_s: int | None = None,
) -> list[Outbound]:
    """Replace the prepared round list (LOBBY only). The host prepares everything
    up front so nothing is typed live on a shared screen. ``buzz_limit_s`` sets the
    per-round buzzer countdown (0 = no limit); ``buzz_answer_s`` the post-buzz answer
    window (0 = no limit); unset keeps the current value."""
    if session.state is not GameState.LOBBY:
        return []
    if buzz_limit_s is not None:
        session.buzz_limit_ms = max(0, int(buzz_limit_s)) * 1000
    if buzz_answer_s is not None:
        session.buzz_answer_ms = max(0, int(buzz_answer_s)) * 1000
    session.rounds = [
        PreparedRound(
            question_text=(item.get("question_text") or None),
            answer=(item.get("answer") or None),
            points=int(item.get("points") or 1),
            bonus=bool(item.get("bonus")),
            image=(item.get("image") or None),
        )
        for item in items
    ]
    session.round_index = -1
    return [_prepared_rounds_outbound(session), *_round_state_outbounds(session)]


def load_round(session: Session, index: int, now: int | None = None) -> list[Outbound]:
    """Open the prepared round at ``index`` (works mid-game, from any state)."""
    if not (0 <= index < len(session.rounds)):
        return []
    if now is None:
        now = now_ms()
    session.round_index = index
    prepared = session.rounds[index]
    return _open_round(
        session, prepared.question_text, prepared.answer, prepared.points, now, prepared.image, prepared.bonus
    )


def start_game(session: Session, now: int | None = None) -> list[Outbound]:
    """Begin the prepared game at the first round."""
    record_game_start(session)
    return load_round(session, 0, now if now is not None else now_ms())


# --------------------------------------------------------------------------- #
# Stats — points won per game (in-memory, session-scoped, mode-agnostic)
# --------------------------------------------------------------------------- #
def record_game_start(session: Session) -> None:
    """Snapshot every player's score at the start of a game so the points won *this
    game* can be reported as a delta at GAME_END (scores are cumulative on a code)."""
    session.game_start_scores = {pid: p.score for pid, p in session.players.items()}


def record_game_end(session: Session, mode: str) -> None:
    """Append a per-game breakdown (points won this game, per player) to game_history."""
    ordered, ranks = _ranked(session)
    results = [
        {
            "id": p.id,
            "pseudo": p.pseudo,
            "points": p.score - session.game_start_scores.get(p.id, 0),
            "total": p.score,
            "rank": ranks[p.id],
        }
        for p in ordered
    ]
    session.game_history.append(
        {"game": len(session.game_history) + 1, "mode": mode, "ts": now_ms(), "results": results}
    )


def stats_payload(session: Session) -> dict:
    """Per-game point history for the stats panel (non-secret, all roles)."""
    return {"history": list(session.game_history)}


def game_end_payload(session: Session) -> dict:
    """Final ranking for the buzzer podium (mirrors qcm.game_end_payload)."""
    ordered, ranks = _ranked(session)
    podium = [
        {"id": p.id, "pseudo": p.pseudo, "score": p.score, "rank": ranks[p.id]} for p in ordered if ranks[p.id] <= 3
    ]
    return {
        "podium": podium,
        "players": player_list_payload(session)["players"],
        "history": list(session.game_history),
    }


def next_action(session: Session, now: int | None = None) -> list[Outbound]:
    """The host "Suivant" button: advance to the next prepared round; once a
    prepared list is exhausted, finish on the podium (GAME_END). An ad-hoc game
    with no prepared list just returns to the lobby."""
    if now is None:
        now = now_ms()
    if session.rounds and session.round_index + 1 < len(session.rounds):
        return load_round(session, session.round_index + 1, now)
    if session.rounds:
        session.state = GameState.GAME_END
        session.revealed = False
        _reset_round_fields(session)  # clear the last round's buzz queue (else it lingers on the TV)
        record_game_end(session, "buzzer")
        logger.info("[{}] buzzer game ended ({} rounds played)", session.code, len(session.rounds))
        return [
            *_round_state_outbounds(session),
            _buzz_outbound(session),
            _player_list_outbound(session),
            Outbound("all", "game_end", game_end_payload(session)),
        ]
    return next_round(session)


def reset_buzzer(session: Session, now: int | None = None) -> list[Outbound]:
    # Once the round is revealed (a correct answer was validated, or the host gave
    # up and showed the answer) the round is over — don't reopen the buzzer.
    if session.revealed:
        return []
    if session.state not in (GameState.BUZZER_OPEN, GameState.BUZZED):
        return []
    if now is None:
        now = now_ms()
    session.state = GameState.BUZZER_OPEN
    session.buzz_open_at = now  # immediate reopen — players have already read it
    _reset_round_fields(session)
    session.buzz_ends_at = now + session.buzz_limit_ms if session.buzz_limit_ms > 0 else 0
    return [*_round_state_outbounds(session), _buzz_outbound(session)]


def validate(session: Session) -> list[Outbound]:
    if session.state is not GameState.BUZZED or session.revealed:
        return []
    player_id = session.floor_player_id
    if player_id is None:
        return []
    awarded = session.points * (2 if session.bonus else 1)
    session.players[player_id].score += awarded
    session.revealed = True
    session.answer_ends_at = 0
    logger.info("[{}] validated {} (+{} pts)", session.code, session.players[player_id].pseudo, awarded)
    reveal = Outbound(
        "all",
        "reveal",
        {
            "answer": session.answer,
            "correct_player_id": player_id,
            "deltas": {player_id: awarded},
        },
    )
    return [*_round_state_outbounds(session), reveal, _player_list_outbound(session)]


def invalidate(session: Session, now: int | None = None) -> list[Outbound]:
    """Wrong oral answer: bar the floor-holder from re-buzzing this round, clear the
    whole queue and reopen the buzzer for a fresh race (no stale "pass the floor")."""
    if session.state is not GameState.BUZZED or session.revealed:
        return []
    wrong = session.floor_player_id
    if wrong is not None:
        session.excluded_ids.add(wrong)
    session.state = GameState.BUZZER_OPEN
    session.buzz_queue = []
    session.buzzed_ids = set()
    session.floor_index = 0
    session.answer_ends_at = 0
    # Buzzer mode: restart the countdown for the reopened (empty) buzzer.
    # (Blindtest reuses this queue logic but drives its own timing.)
    if session.mode is GameMode.BUZZER:
        if now is None:
            now = now_ms()
        session.buzz_open_at = now
        session.buzz_ends_at = now + session.buzz_limit_ms if session.buzz_limit_ms > 0 else 0
    return [*_round_state_outbounds(session), _buzz_outbound(session)]


def reveal(session: Session) -> list[Outbound]:
    if session.state not in (GameState.BUZZER_OPEN, GameState.BUZZED):
        return []
    session.revealed = True
    session.answer_ends_at = 0
    reveal = Outbound("all", "reveal", {"answer": session.answer, "correct_player_id": None, "deltas": {}})
    return [*_round_state_outbounds(session), reveal]


def next_round(session: Session) -> list[Outbound]:
    session.state = GameState.LOBBY
    session.question_text = None
    session.answer = None
    session.points = 1
    session.bonus = False
    session.image = None
    session.round_index = -1
    _reset_round_fields(session)
    return [*_round_state_outbounds(session), _buzz_outbound(session)]


def return_to_lobby(session: Session) -> bool:
    """Send a finished game back to the lobby, keeping players (and their scores)
    on the same code so the host can pick packs again for the next round.

    Acts only from GAME_END (any mode). Scores are **kept** (cumulative across
    rounds on the same code — a player who leaves and rejoins via their
    reconnect_token keeps their total); only the per-round streak/rank bookkeeping
    is reset. The session drops back to the default buzzer mode in LOBBY and every
    prepared list is cleared. Returns whether it acted, so the caller can broadcast
    a fresh state_sync to move all clients back to the preparation screen."""
    if session.state is not GameState.GAME_END:
        return False
    for p in session.players.values():
        p.streak = 0
        p.last_rank = 0
    session.mode = GameMode.BUZZER
    session.state = GameState.LOBBY
    session.rounds = []
    session.round_index = -1
    session.qcm_rounds = []
    session.qcm_index = -1
    session.blindtest_tracks = []
    session.bt_index = -1
    _reset_round_fields(session)
    logger.info("[{}] return to lobby ({} players, scores kept)", session.code, len(session.players))
    return True


def adjust_score(session: Session, player_id: str | None, delta: int) -> list[Outbound]:
    player = session.players.get(player_id or "")
    if player is None:
        return []
    player.score += delta
    return [_player_list_outbound(session)]


def kick(session: Session, player_id: str | None) -> list[Outbound]:
    player = session.players.pop(player_id or "", None)
    if player is None:
        return []
    outs: list[Outbound] = [Outbound(player.id, "error", {"code": "kicked", "message": "Vous avez été exclu."})]
    outs += _advance_floor_if_departed(session, player.id)
    outs.append(_player_list_outbound(session))
    return outs


def handle_host_action(session: Session, action: str, payload: dict, now: int | None = None) -> list[Outbound]:
    """Dispatch a ``host_action`` message to the matching handler."""
    if now is None:
        now = now_ms()
    match action:
        case "open_buzzer":
            limit = payload.get("buzz_limit_s")
            if limit is not None:
                try:
                    session.buzz_limit_ms = max(0, int(limit)) * 1000
                except (TypeError, ValueError):
                    pass
            answer_limit = payload.get("buzz_answer_s")
            if answer_limit is not None:
                try:
                    session.buzz_answer_ms = max(0, int(answer_limit)) * 1000
                except (TypeError, ValueError):
                    pass
            return open_buzzer(
                session,
                now,
                payload.get("question_text"),
                payload.get("answer"),
                payload.get("points"),
            )
        case "set_rounds":
            items = payload.get("rounds")
            if not isinstance(items, list):
                return []
            limit = payload.get("buzz_limit_s")
            try:
                limit_s = int(limit) if limit is not None else None
            except (TypeError, ValueError):
                limit_s = None
            answer = payload.get("buzz_answer_s")
            try:
                answer_s = int(answer) if answer is not None else None
            except (TypeError, ValueError):
                answer_s = None
            return set_rounds(session, items, buzz_limit_s=limit_s, buzz_answer_s=answer_s)
        case "load_round":
            try:
                return load_round(session, int(payload.get("index")), now)
            except (TypeError, ValueError):
                return []
        case "start" | "start_game":
            return start_game(session, now)
        case "reset_buzzer":
            return reset_buzzer(session, now)
        case "validate":
            return validate(session)
        case "invalidate":
            return invalidate(session)
        case "reveal":
            return reveal(session)
        case "next" | "skip":
            return next_action(session, now)
        case "end":
            return next_round(session)
        case "adjust_score":
            try:
                delta = int(payload.get("delta", 0))
            except (TypeError, ValueError):
                return []
            return adjust_score(session, payload.get("player_id"), delta)
        case "kick":
            return kick(session, payload.get("player_id"))
        case _:
            return []
