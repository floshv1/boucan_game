"""Unit tests for the pure buzzer engine (cahier §14)."""

from __future__ import annotations

from game import engine
from game import store as store_mod
from game.models import GameMode, GameState
from game.store import CODE_ALPHABET, SessionStore, generate_code, now_ms


def _by_type(outs, type_):
    return [o for o in outs if o.type == type_]


def _new_session_with_players(*pseudos):
    store = SessionStore()
    session = store.create()
    players = []
    for pseudo in pseudos:
        player, _ = engine.join(session, pseudo)
        players.append(player)
    return session, players


def test_return_to_lobby_resets_from_game_end():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    alice.score = 12
    alice.streak = 3
    session.mode = GameMode.QCM
    session.qcm_rounds = ["x", "y"]  # type: ignore[list-item]
    session.qcm_index = 1
    session.state = GameState.GAME_END

    assert engine.return_to_lobby(session) is True
    assert session.state is GameState.LOBBY
    assert session.mode is GameMode.BUZZER
    assert alice.score == 12 and alice.streak == 0  # scores kept, streak reset
    assert session.qcm_rounds == [] and session.qcm_index == -1
    assert session.blindtest_tracks == [] and session.bt_index == -1


def test_return_to_lobby_noop_outside_game_end():
    session, _ = _new_session_with_players("Alice")
    assert engine.return_to_lobby(session) is False


def test_reading_window_set_only_for_text_rounds():
    session, _ = _new_session_with_players("Alice")
    engine.READING_MS = 5000
    try:
        engine.open_buzzer(session, now=1000, question_text="Q ?", answer="A", points=1)
        assert session.buzz_open_at == 6000  # 1000 + 5000 reading
        session.state = GameState.LOBBY
        engine.open_buzzer(session, now=2000)  # no text → immediate
        assert session.buzz_open_at == 2000
    finally:
        engine.READING_MS = 0


def test_buzzer_prepared_game_ends_on_podium():
    session, [alice] = _new_session_with_players("Alice")
    engine.set_rounds(session, [{"question_text": "Q1", "answer": "A1", "points": 1}])
    engine.start_game(session, now=0)
    alice.score = 4
    outs = engine.next_action(session, now=1000)  # past the only prepared round
    assert session.state is GameState.GAME_END
    rs = [o for o in outs if o.type == "round_state" and o.target == "players"][0].payload
    assert rs["state"] == "GAME_END"
    assert alice.score == 4  # scores kept for the podium


def test_reset_buzzer_blocked_after_reveal():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session, now=0, question_text="Q", answer="A", points=1)
    engine.buzz(session, alice.id, now=1000)
    engine.validate(session)  # revealed = True
    assert engine.reset_buzzer(session, now=2000) == []
    assert session.revealed is True


# --------------------------------------------------------------------------- #
# Session codes
# --------------------------------------------------------------------------- #
def test_generate_code_shape():
    code = generate_code(set())
    assert len(code) == 6
    assert all(c in CODE_ALPHABET for c in code)


def test_generate_code_avoids_collisions():
    existing = {generate_code(set()) for _ in range(50)}
    code = generate_code(existing)
    assert code not in existing


def test_create_session_starts_in_lobby():
    store = SessionStore()
    session = store.create()
    assert session.state is GameState.LOBBY
    assert session.host_secret
    assert store.get(session.code) is session
    assert store.get(session.code.lower()) is session  # case-insensitive lookup


def test_has_host_secret_constant_time_lookup():
    store = SessionStore()
    s = store.create()
    assert store.has_host_secret(s.host_secret) is True
    assert store.has_host_secret("nope") is False
    assert store.has_host_secret("") is False


def test_store_evicts_idle_sessions_on_create():
    store = SessionStore()
    idle = store.create()
    idle.last_seen = now_ms() - store_mod.SESSION_TTL_MS - 1  # abandoned past the TTL
    active = store.create()
    active.last_seen = now_ms()  # still warm (would be refreshed by pings)
    store.create()  # any new creation runs eviction
    assert store.get(idle.code) is None  # idle one evicted
    assert store.get(active.code) is active  # active one kept


# --------------------------------------------------------------------------- #
# Joining
# --------------------------------------------------------------------------- #
def test_join_creates_player_and_broadcasts_list():
    session, _ = _new_session_with_players()
    player, outs = engine.join(session, "Alice")
    assert player.id in session.players
    assert player.score == 0
    assert _by_type(outs, "state_sync")
    assert _by_type(outs, "player_list")


def test_join_duplicate_pseudo_gets_suffix():
    session, _ = _new_session_with_players("Bob")
    player, _ = engine.join(session, "Bob")
    assert player.pseudo == "Bob (2)"


def test_join_with_reconnect_token_reattaches_same_player():
    session, [alice] = _new_session_with_players("Alice")
    alice.score = 7
    alice.connected = False

    same, outs = engine.join(session, "ignored", reconnect_token=alice.reconnect_token)
    assert same.id == alice.id
    assert same.score == 7
    assert same.connected is True
    assert len(session.players) == 1  # no duplicate created


# --------------------------------------------------------------------------- #
# Buzz arbitration
# --------------------------------------------------------------------------- #
def test_first_buzz_locks_the_floor():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session)

    outs = engine.buzz(session, alice.id, now=1000)
    assert session.state is GameState.BUZZED
    assert session.floor_player_id == alice.id
    queue = _by_type(outs, "buzz_locked")[0].payload["queue"]
    assert queue[0]["order"] == 1
    assert queue[0]["delta_ms"] == 0


def test_second_buzz_is_queued_with_delta():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)

    outs = engine.buzz(session, bob.id, now=1150)
    assert session.floor_player_id == alice.id  # floor unchanged
    queue = _by_type(outs, "buzz_locked")[0].payload["queue"]
    assert [e["order"] for e in queue] == [1, 2]
    assert queue[1]["delta_ms"] == 150


def test_same_player_cannot_buzz_twice():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)

    outs = engine.buzz(session, alice.id, now=1200)
    assert outs == []
    assert len(session.buzz_queue) == 1


def test_buzz_ignored_outside_open_states():
    session, [alice] = _new_session_with_players("Alice")
    # still in LOBBY
    assert engine.buzz(session, alice.id, now=1000) == []
    assert session.state is GameState.LOBBY


def test_uses_server_timestamp_not_client():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=5000)
    assert session.buzz_queue[0].ts == 5000


# --------------------------------------------------------------------------- #
# Host validate / invalidate
# --------------------------------------------------------------------------- #
def test_validate_awards_points_and_reveals():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session, question_text="Capitale de la France ?", answer="Paris", points=3)
    engine.buzz(session, alice.id, now=1000)

    outs = engine.validate(session)
    assert session.players[alice.id].score == 3
    assert session.revealed is True
    reveal = _by_type(outs, "reveal")[0].payload
    assert reveal["answer"] == "Paris"
    assert reveal["correct_player_id"] == alice.id


def test_bonus_round_doubles_points():
    session, [alice] = _new_session_with_players("Alice")
    engine.set_rounds(session, [{"question_text": "Q", "answer": "A", "points": 3, "bonus": True}])
    engine.load_round(session, 0)
    engine.buzz(session, alice.id, now=1000)
    outs = engine.validate(session)
    assert session.players[alice.id].score == 6  # 3 × 2
    assert _by_type(outs, "reveal")[0].payload["deltas"][alice.id] == 6


def test_invalidate_resets_queue_and_bars_wrong_player():
    # A wrong answer no longer "passes the floor": the queue is wiped and the buzzer
    # reopens for a fresh race, with the fautif barred from buzzing again this round.
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)
    engine.buzz(session, bob.id, now=1100)

    engine.invalidate(session)
    assert session.state is GameState.BUZZER_OPEN
    assert session.floor_player_id is None
    assert session.buzz_queue == []
    assert alice.id in session.excluded_ids
    assert session.players[alice.id].score == 0

    # Alice can't re-buzz; Bob (and anyone else) can.
    engine.buzz(session, alice.id, now=1200)
    assert session.floor_player_id is None
    engine.buzz(session, bob.id, now=1300)
    assert session.floor_player_id == bob.id


def test_invalidate_reopens_when_queue_exhausted():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)

    engine.invalidate(session)
    assert session.state is GameState.BUZZER_OPEN
    assert session.floor_player_id is None


def test_new_round_clears_exclusions():
    session, [alice] = _new_session_with_players("Alice")
    engine.set_rounds(session, [{"question_text": "Q1", "answer": "A", "points": 1}, {"question_text": "Q2", "answer": "B", "points": 1}])
    engine.load_round(session, 0)
    engine.buzz(session, alice.id, now=1000)
    engine.invalidate(session)
    assert alice.id in session.excluded_ids
    engine.load_round(session, 1)
    assert session.excluded_ids == set()
    engine.buzz(session, alice.id, now=2000)
    assert session.floor_player_id == alice.id


# --------------------------------------------------------------------------- #
# Post-buzz answer window (answer_ends_at)
# --------------------------------------------------------------------------- #
def test_buzz_arms_answer_window():
    session, [alice] = _new_session_with_players("Alice")
    session.buzz_answer_ms = 7000
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)
    assert session.answer_ends_at == 1000 + 7000


def test_answer_window_zero_means_no_deadline():
    session, [alice] = _new_session_with_players("Alice")
    session.buzz_answer_ms = 0
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)
    assert session.answer_ends_at == 0


def test_answer_window_cleared_on_validate_and_invalidate():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session, answer=None, points=1)
    engine.buzz(session, alice.id, now=1000)
    assert session.answer_ends_at > 0
    engine.invalidate(session)  # reopen → no floor → window cleared
    assert session.answer_ends_at == 0
    engine.buzz(session, bob.id, now=1100)
    assert session.answer_ends_at > 0
    engine.validate(session)
    assert session.answer_ends_at == 0


def test_set_rounds_stores_buzz_answer_limit():
    session, _ = _new_session_with_players("Alice")
    engine.set_rounds(session, [{"question_text": "Q", "answer": "A", "points": 1}], buzz_answer_s=12)
    assert session.buzz_answer_ms == 12000


# --------------------------------------------------------------------------- #
# Stats — points won per game
# --------------------------------------------------------------------------- #
def test_game_history_records_points_per_game():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    bob.score = 5  # pre-existing cumulative score from an earlier game
    engine.set_rounds(session, [{"question_text": "Q", "answer": "A", "points": 3}])
    engine.start_game(session)  # snapshots {alice:0, bob:5}
    engine.buzz(session, alice.id, now=1000)
    engine.validate(session)  # alice +3
    engine.next_action(session)  # → GAME_END, records the game

    assert len(session.game_history) == 1
    entry = session.game_history[0]
    assert entry["mode"] == "buzzer"
    by_pseudo = {r["pseudo"]: r for r in entry["results"]}
    assert by_pseudo["Alice"]["points"] == 3  # delta this game
    assert by_pseudo["Alice"]["total"] == 3
    assert by_pseudo["Bob"]["points"] == 0  # didn't score this game
    assert by_pseudo["Bob"]["total"] == 5


# --------------------------------------------------------------------------- #
# Buzzer countdown (buzz_ends_at) — auto-reveal when nobody buzzes
# --------------------------------------------------------------------------- #
def test_buzz_ends_at_set_from_open_after_reading_window():
    session, _ = _new_session_with_players("Alice")
    engine.READING_MS = 3000
    try:
        session.buzz_limit_ms = 20000
        engine.open_buzzer(session, now=1000, question_text="Q ?", answer="A", points=1)
        # opens at 1000+3000 reading, then 20s limit → 24000
        assert session.buzz_open_at == 4000
        assert session.buzz_ends_at == 24000
    finally:
        engine.READING_MS = 0


def test_buzz_limit_zero_means_no_deadline():
    session, _ = _new_session_with_players("Alice")
    session.buzz_limit_ms = 0
    engine.open_buzzer(session, now=0)
    assert session.buzz_ends_at == 0


def test_set_rounds_stores_buzz_limit():
    session, _ = _new_session_with_players("Alice")
    engine.set_rounds(session, [{"question_text": "Q", "answer": "A", "points": 1}], buzz_limit_s=15)
    assert session.buzz_limit_ms == 15000


def test_buzz_ends_at_cleared_on_game_end_and_lobby():
    session, [alice] = _new_session_with_players("Alice")
    engine.set_rounds(session, [{"question_text": "Q1", "answer": "A1", "points": 1}])
    engine.start_game(session, now=0)
    assert session.buzz_ends_at > 0
    engine.next_action(session, now=1000)  # exhaust → GAME_END
    assert session.state is GameState.GAME_END
    assert session.buzz_ends_at == 0


def test_invalidate_restarts_buzzer_countdown():
    session, [alice] = _new_session_with_players("Alice")
    session.buzz_limit_ms = 20000
    engine.open_buzzer(session, now=0)  # no text → opens now, ends at 20000
    engine.buzz(session, alice.id, now=1000)  # → BUZZED, countdown paused
    engine.invalidate(session, now=5000)  # wrong → reopen, fresh countdown from 5000
    assert session.state is GameState.BUZZER_OPEN
    assert session.buzz_ends_at == 25000


def test_floor_holder_departure_restarts_buzzer_countdown():
    """Kicking/disconnecting the floor-holder reopens the buzzer with a fresh
    countdown (not the stale open deadline, which would auto-reveal instantly)."""
    from game.store import now_ms

    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    session.buzz_limit_ms = 20000
    engine.open_buzzer(session, now=0)  # logical deadline 20000 — already past in real time
    engine.buzz(session, alice.id, now=1000)  # alice holds the floor
    engine.kick(session, alice.id)  # floor-holder leaves → reopen
    assert session.state is GameState.BUZZER_OPEN
    assert session.buzz_ends_at >= now_ms()  # refreshed to a future real-clock deadline


# --------------------------------------------------------------------------- #
# Answer filtering by role (cahier §16)
# --------------------------------------------------------------------------- #
def test_answer_hidden_from_players_until_reveal():
    session, [alice] = _new_session_with_players("Alice")
    outs = engine.open_buzzer(session, question_text="Q", answer="SECRET", points=1)

    host_state = [o for o in outs if o.type == "round_state" and o.target == "host"][0]
    players_state = [o for o in outs if o.type == "round_state" and o.target == "players"][0]
    assert host_state.payload["answer"] == "SECRET"
    assert players_state.payload["answer"] is None
    assert players_state.payload["question_text"] == "Q"


def test_answer_revealed_to_players_after_validate():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session, answer="SECRET", points=1)
    engine.buzz(session, alice.id, now=1000)
    outs = engine.validate(session)

    players_state = [o for o in outs if o.type == "round_state" and o.target == "players"][0]
    assert players_state.payload["answer"] == "SECRET"


# --------------------------------------------------------------------------- #
# Manual scoring, kick, departures
# --------------------------------------------------------------------------- #
def test_adjust_score_changes_score():
    session, [alice] = _new_session_with_players("Alice")
    engine.adjust_score(session, alice.id, 5)
    engine.adjust_score(session, alice.id, -2)
    assert session.players[alice.id].score == 3


def test_kick_removes_player_and_advances_floor():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)
    engine.buzz(session, bob.id, now=1100)

    outs = engine.kick(session, alice.id)
    assert alice.id not in session.players
    assert session.floor_player_id == bob.id
    assert _by_type(outs, "error")  # the kicked player is notified


def test_disconnect_of_floor_player_frees_the_floor():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)
    engine.buzz(session, bob.id, now=1100)

    engine.on_disconnect(session, alice.id)
    assert session.players[alice.id].connected is False  # kept for reconnection
    assert session.floor_player_id == bob.id


def test_next_round_returns_to_lobby_and_clears():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session, question_text="Q", answer="A", points=2)
    engine.buzz(session, alice.id, now=1000)
    engine.validate(session)

    engine.next_round(session)
    assert session.state is GameState.LOBBY
    assert session.question_text is None
    assert session.answer is None
    assert session.buzz_queue == []
    assert session.players[alice.id].score == 2  # scores persist across rounds


def test_ranking_ties_share_rank():
    session, [alice, bob, carol] = _new_session_with_players("Alice", "Bob", "Carol")
    session.players[alice.id].score = 10
    session.players[bob.id].score = 10
    session.players[carol.id].score = 5

    payload = engine.player_list_payload(session)
    ranks = {p["pseudo"]: p["rank"] for p in payload["players"]}
    assert ranks["Alice"] == 1
    assert ranks["Bob"] == 1
    assert ranks["Carol"] == 3


# --------------------------------------------------------------------------- #
# Prepared round list (itération 2)
# --------------------------------------------------------------------------- #
_THREE_ROUNDS = [
    {"question_text": "Capitale de la France ?", "answer": "Paris", "points": 1},
    {"question_text": None, "answer": "Daft Punk", "points": 2},  # blindtest: no text
    {"question_text": "Année de sortie de X ?", "answer": "1999", "points": 1},
]


def test_set_rounds_stores_list_and_is_host_only():
    session, _ = _new_session_with_players()
    outs = engine.set_rounds(session, _THREE_ROUNDS)

    assert len(session.rounds) == 3
    assert session.round_index == -1
    assert session.state is GameState.LOBBY

    # The full list (with answers) goes ONLY to the host, never to players/TV.
    prepared = _by_type(outs, "prepared_rounds")
    assert prepared and all(o.target == "host" for o in prepared)
    assert prepared[0].payload["rounds"][0]["answer"] == "Paris"
    assert not [o for o in outs if o.type == "prepared_rounds" and o.target != "host"]


def test_set_rounds_rejected_outside_lobby():
    session, _ = _new_session_with_players()
    engine.set_rounds(session, _THREE_ROUNDS)
    engine.start_game(session)  # now BUZZER_OPEN
    assert engine.set_rounds(session, _THREE_ROUNDS[:1]) == []
    assert len(session.rounds) == 3  # unchanged


def test_start_game_loads_first_prepared_round():
    session, _ = _new_session_with_players()
    engine.set_rounds(session, _THREE_ROUNDS)
    engine.start_game(session)

    assert session.round_index == 0
    assert session.state is GameState.BUZZER_OPEN
    assert session.question_text == "Capitale de la France ?"
    assert session.answer == "Paris"
    assert session.points == 1


def test_next_advances_through_prepared_rounds_then_lobby():
    session, [alice] = _new_session_with_players("Alice")
    engine.set_rounds(session, _THREE_ROUNDS)
    engine.start_game(session)

    engine.next_action(session)
    assert session.round_index == 1
    assert session.question_text is None  # blindtest round, no text
    assert session.answer == "Daft Punk"
    assert session.points == 2

    engine.next_action(session)
    assert session.round_index == 2
    assert session.answer == "1999"

    engine.next_action(session)  # past the last prepared round → podium
    assert session.state is GameState.GAME_END


def test_round_state_carries_index_and_total():
    session, _ = _new_session_with_players()
    engine.set_rounds(session, _THREE_ROUNDS)
    outs = engine.start_game(session)
    players_state = [o for o in outs if o.type == "round_state" and o.target == "players"][0].payload
    assert players_state["round_index"] == 0
    assert players_state["round_total"] == 3


def test_load_round_works_mid_game_and_keeps_answer_hidden_from_players():
    session, [alice] = _new_session_with_players("Alice")
    engine.set_rounds(session, _THREE_ROUNDS)
    engine.start_game(session)
    engine.buzz(session, alice.id, now=1000)  # state BUZZED

    outs = engine.load_round(session, 1)  # jump to round 1 from BUZZED
    assert session.state is GameState.BUZZER_OPEN
    assert session.buzz_queue == []  # round fields reset
    players_state = [o for o in outs if o.type == "round_state" and o.target == "players"][0].payload
    assert players_state["answer"] is None
    host_state = [o for o in outs if o.type == "round_state" and o.target == "host"][0].payload
    assert host_state["answer"] == "Daft Punk"


# --------------------------------------------------------------------------- #
# TV spectator role (itération 2) — never receives the answer
# --------------------------------------------------------------------------- #
def test_tv_state_sync_omits_answer():
    session, _ = _new_session_with_players()
    engine.set_rounds(session, _THREE_ROUNDS)
    engine.start_game(session)  # answer "Paris" is live for the host

    out = engine.state_sync_outbound(session, role="tv")
    assert out.payload["you"]["role"] == "tv"
    assert out.payload["round"]["answer"] is None
    assert out.payload["round"]["question_text"] == "Capitale de la France ?"
    # no reconnect token for a spectator
    assert "reconnect_token" not in out.payload["you"]


def test_prepared_round_carries_image_and_reaches_round_state():
    session, _ = _new_session_with_players()
    outs = engine.set_rounds(
        session,
        [{"question_text": "Q", "answer": "A", "points": 1, "image": "/media/y.webp"}],
    )
    prep = _by_type(outs, "prepared_rounds")[0]
    assert prep.payload["rounds"][0]["image"] == "/media/y.webp"
    # Open the prepared round and confirm round_state carries the image to host + players.
    open_outs = engine.load_round(session, 0)
    rs = _by_type(open_outs, "round_state")
    assert rs, "expected round_state outbounds"
    assert all(o.payload.get("image") == "/media/y.webp" for o in rs)
