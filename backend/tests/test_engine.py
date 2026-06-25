"""Unit tests for the pure buzzer engine (cahier §14)."""

from __future__ import annotations

from game import engine
from game.models import GameState
from game.store import CODE_ALPHABET, SessionStore, generate_code


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


def test_invalidate_passes_floor_to_next():
    session, [alice, bob] = _new_session_with_players("Alice", "Bob")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)
    engine.buzz(session, bob.id, now=1100)

    engine.invalidate(session)
    assert session.floor_player_id == bob.id
    assert session.players[alice.id].score == 0


def test_invalidate_reopens_when_queue_exhausted():
    session, [alice] = _new_session_with_players("Alice")
    engine.open_buzzer(session)
    engine.buzz(session, alice.id, now=1000)

    engine.invalidate(session)
    assert session.state is GameState.BUZZER_OPEN
    assert session.floor_player_id is None


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

    engine.next_action(session)  # past the last prepared round
    assert session.state is GameState.LOBBY
    assert session.round_index == -1


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
