"""Pure game logic for Phase 2 (QCM mode, cahier §4.3).

Like ``game/engine.py`` this module never touches the network: each function
mutates a :class:`Session` and returns a list of :class:`engine.Outbound`
messages. The per-question countdown lives in the async layer (``main.py``);
this module is given ``now`` and stays deterministic for tests.

Targets (see engine.Outbound): "all" | "host" | "players" | <player_id>.
Note: the "players" target also reaches TV spectators (see ws/manager.py), so
``correct`` is never put on a "players"/"all" payload before REVEAL (§16).
"""

from __future__ import annotations

import random

from game.engine import Outbound, _ranked, player_list_payload
from game.models import GameMode, GameState, QcmAnswer, QcmRound, Session


def prepared_qcm_payload(session: Session) -> dict:
    """Full prepared list WITH correct answers — host only."""
    return {
        "index": session.qcm_index,
        "shuffle_questions": session.qcm_shuffle_questions,
        "shuffle_choices": session.qcm_shuffle_choices,
        "rounds": [
            {
                "question": r.question,
                "choices": list(r.choices),
                "correct": r.correct,
                "time_limit": r.time_limit,
                "points": r.points,
                "image": r.image,
            }
            for r in session.qcm_rounds
        ],
    }


def _parse_round(item: dict) -> QcmRound:
    choices = [str(c) for c in (item.get("choices") or [])][:4]
    while len(choices) < 4:
        choices.append("")
    try:
        correct = int(item.get("correct", 0))
    except (TypeError, ValueError):
        correct = 0
    correct = correct if 0 <= correct < 4 else 0
    return QcmRound(
        question=str(item.get("question") or ""),
        choices=choices,
        correct=correct,
        time_limit=max(5, int(item.get("time_limit") or 20)),
        points=max(1, int(item.get("points") or 1000)),
        bonus=bool(item.get("bonus")),
        image=(str(item["image"]) if item.get("image") else None),
    )


def set_qcm_rounds(
    session: Session,
    items: list[dict],
    *,
    shuffle_questions: bool = False,
    shuffle_choices: bool = False,
) -> list[Outbound]:
    """Replace the prepared QCM list (LOBBY only) and switch the session to QCM
    mode. The full list (with answers) goes only to the host."""
    if session.state is not GameState.LOBBY:
        return []
    session.mode = GameMode.QCM
    session.qcm_rounds = [_parse_round(it) for it in items]
    session.qcm_index = -1
    session.qcm_shuffle_questions = bool(shuffle_questions)
    session.qcm_shuffle_choices = bool(shuffle_choices)
    return [
        Outbound("host", "prepared_qcm", prepared_qcm_payload(session)),
        Outbound("all", "player_list", player_list_payload(session)),
    ]


def _present(session: Session) -> tuple[QcmRound, list[str], int]:
    """Return (round, presented_choices, presented_correct_index) for the
    current question, honouring ``presented_order``."""
    rnd = session.qcm_rounds[session.qcm_index]
    presented_choices = [rnd.choices[i] for i in session.presented_order]
    presented_correct = session.presented_order.index(rnd.correct)
    return rnd, presented_choices, presented_correct


def question_start_payload(session: Session, *, include_correct: bool) -> dict:
    rnd, choices, presented_correct = _present(session)
    payload = {
        "index": session.qcm_index,
        "total": len(session.qcm_rounds),
        "question": rnd.question,
        "choices": choices,
        "time_limit": rnd.time_limit,
        "ends_at": session.question_ends_at,
        "points": rnd.points,
        "bonus": rnd.bonus,
        "image": rnd.image,
    }
    if include_correct:
        payload["correct"] = presented_correct
    return payload


def qcm_progress_payload(session: Session) -> dict:
    total = sum(1 for p in session.players.values() if p.connected)
    return {"answered": len(session.answers), "total": total}


def _question_start_outbounds(session: Session) -> list[Outbound]:
    return [
        Outbound("host", "question_start", question_start_payload(session, include_correct=True)),
        Outbound("players", "question_start", question_start_payload(session, include_correct=False)),
        Outbound("all", "qcm_progress", qcm_progress_payload(session)),
    ]


def load_question(session: Session, index: int, now: int) -> list[Outbound]:
    if not (0 <= index < len(session.qcm_rounds)):
        return []
    rnd = session.qcm_rounds[index]
    session.qcm_index = index
    session.state = GameState.QUESTION_ACTIVE
    session.question_started_at = now
    session.question_ends_at = now + rnd.time_limit * 1000
    session.answers = {}
    order = [0, 1, 2, 3]
    if session.qcm_shuffle_choices:
        random.shuffle(order)
    session.presented_order = order
    return _question_start_outbounds(session)


def start_qcm(session: Session, now: int) -> list[Outbound]:
    if session.state is not GameState.LOBBY or not session.qcm_rounds:
        return []
    if session.qcm_shuffle_questions:
        random.shuffle(session.qcm_rounds)
    for p in session.players.values():
        p.streak = 0
        p.last_rank = 0
    return load_question(session, 0, now)


def all_answered(session: Session) -> bool:
    connected = [pid for pid, p in session.players.items() if p.connected]
    return bool(connected) and all(pid in session.answers for pid in connected)


def answer_submit(session: Session, player_id: str, choice: int, now: int) -> list[Outbound]:
    if session.state is not GameState.QUESTION_ACTIVE:
        return []
    if player_id not in session.players or player_id in session.answers:
        return []
    if not (0 <= int(choice) < 4):
        return []
    session.answers[player_id] = QcmAnswer(choice=int(choice), ts=now)
    return [
        Outbound(player_id, "answer_ack", {"choice": int(choice)}),
        Outbound("all", "qcm_progress", qcm_progress_payload(session)),
    ]


def _speed_factor(t: float, limit: int) -> float:
    """1.0 at t=0 → 0.5 at t=limit (clamped)."""
    t = max(0.0, min(float(t), float(limit)))
    return max(0.5, min(1.0, 1.0 - (t / limit) / 2.0))


def _streak_mult(streak_after: int) -> float:
    """+10% per consecutive correct, capped at +50% (cahier-validated)."""
    return 1.0 + min((max(streak_after, 1) - 1) * 0.10, 0.50)


def reveal(session: Session, *, award: bool = True) -> list[Outbound]:
    if session.state is not GameState.QUESTION_ACTIVE:
        return []
    rnd, _choices, presented_correct = _present(session)
    distribution = [0, 0, 0, 0]
    deltas: dict[str, int] = {}

    for pid, player in session.players.items():
        ans = session.answers.get(pid)
        if ans is not None and 0 <= ans.choice < 4:
            distribution[ans.choice] += 1
        if not award:
            continue
        is_correct = ans is not None and ans.choice == presented_correct
        if is_correct:
            t = (ans.ts - session.question_started_at) / 1000.0
            player.streak += 1
            base = rnd.points * (2 if rnd.bonus else 1)
            awarded = round(base * _speed_factor(t, rnd.time_limit) * _streak_mult(player.streak))
            player.score += awarded
            ans.correct = True
            ans.awarded = awarded
            deltas[pid] = awarded
        else:
            player.streak = 0

    session.state = GameState.REVEAL
    reveal_payload = {"correct": presented_correct, "distribution": distribution, "deltas": deltas}
    reveal_out = Outbound("all", "reveal", reveal_payload)
    return [reveal_out, Outbound("all", "player_list", player_list_payload(session))]


def _board_rows(session: Session) -> list[dict]:
    ordered, ranks = _ranked(session)
    rows = []
    for p in ordered:
        rank = ranks[p.id]
        rows.append(
            {
                "id": p.id,
                "pseudo": p.pseudo,
                "score": p.score,
                "rank": rank,
                "delta": (p.last_rank - rank) if p.last_rank else 0,
            }
        )
    return rows


def to_scoreboard(session: Session) -> list[Outbound]:
    if session.state is not GameState.REVEAL:
        return []
    rows = _board_rows(session)
    for row in rows:  # remember ranks for next time's ▲/▼
        session.players[row["id"]].last_rank = row["rank"]
    session.state = GameState.SCOREBOARD
    return [Outbound("all", "scoreboard", {"players": rows})]


def game_end_payload(session: Session) -> dict:
    ordered, ranks = _ranked(session)
    podium = [
        {"id": p.id, "pseudo": p.pseudo, "score": p.score, "rank": ranks[p.id]} for p in ordered if ranks[p.id] <= 3
    ]
    return {"podium": podium, "players": player_list_payload(session)["players"]}


def next_(session: Session, now: int) -> list[Outbound]:
    if session.state is not GameState.SCOREBOARD:
        return []
    if session.qcm_index + 1 < len(session.qcm_rounds):
        return load_question(session, session.qcm_index + 1, now)
    session.state = GameState.GAME_END
    return [Outbound("all", "game_end", game_end_payload(session))]


def replay_game(session: Session, now: int) -> list[Outbound]:
    """Restart the QCM from the first question with scores reset (GAME_END only),
    so the host can replay the same set without recreating the game."""
    if session.state is not GameState.GAME_END:
        return []
    for p in session.players.values():
        p.score = 0
        p.streak = 0
        p.last_rank = 0
    session.state = GameState.LOBBY  # let start_qcm's guard pass
    session.qcm_index = -1
    return [
        Outbound("all", "player_list", player_list_payload(session)),
        *start_qcm(session, now),
    ]


def state_sync_payload(session: Session, *, role: str, player_id: str | None = None) -> dict:
    """QCM section embedded in the global state_sync (cahier §13 reconnection)."""
    data: dict = {
        "mode": session.mode.value,
        "state": session.state.value,
        "index": session.qcm_index,
        "total": len(session.qcm_rounds),
    }
    if session.state is GameState.QUESTION_ACTIVE:
        data["question"] = question_start_payload(session, include_correct=(role == "host"))
        data["progress"] = qcm_progress_payload(session)
        data["my_choice"] = session.answers[player_id].choice if (player_id and player_id in session.answers) else None
    elif session.state is GameState.GAME_END:
        data["game_end"] = game_end_payload(session)
    return data
