"""Unit tests for the pure QCM engine (cahier §4.3, Phase 2)."""

from __future__ import annotations

from game import qcm
from game.models import GameMode, GameState
from game.store import SessionStore


def _by_type(outs, type_):
    return [o for o in outs if o.type == type_]


def _session_with_players(*pseudos):
    from game import engine

    store = SessionStore()
    session = store.create()
    players = [engine.join(session, p)[0] for p in pseudos]
    return session, players


_TWO_QCM = [
    {
        "question": "Année de Matrix ?",
        "choices": ["1997", "1999", "2001", "2003"],
        "correct": 1,
        "time_limit": 20,
        "points": 1000,
    },
    {
        "question": "Plus grand océan ?",
        "choices": ["Atlantique", "Indien", "Pacifique", "Arctique"],
        "correct": 2,
        "time_limit": 15,
        "points": 1000,
    },
]


def test_set_qcm_rounds_stores_list_sets_mode_and_is_host_only():
    session, _ = _session_with_players()
    outs = qcm.set_qcm_rounds(session, _TWO_QCM, shuffle_questions=False, shuffle_choices=False)

    assert session.mode is GameMode.QCM
    assert len(session.qcm_rounds) == 2
    assert session.qcm_rounds[0].correct == 1
    assert session.qcm_index == -1
    assert session.state is GameState.LOBBY

    prepared = _by_type(outs, "prepared_qcm")
    assert prepared and all(o.target == "host" for o in prepared)
    assert prepared[0].payload["rounds"][0]["correct"] == 1
    # never broadcast with answers
    assert not [o for o in outs if o.type == "prepared_qcm" and o.target != "host"]


def test_set_qcm_rounds_rejected_outside_lobby():
    session, _ = _session_with_players()
    qcm.set_qcm_rounds(session, _TWO_QCM)
    session.state = GameState.QUESTION_ACTIVE
    assert qcm.set_qcm_rounds(session, _TWO_QCM[:1]) == []
    assert len(session.qcm_rounds) == 2


def test_start_qcm_opens_first_question_and_hides_correct_from_players():
    session, _ = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    outs = qcm.start_qcm(session, now=1_000)

    assert session.state is GameState.QUESTION_ACTIVE
    assert session.qcm_index == 0
    assert session.question_started_at == 1_000
    assert session.question_ends_at == 1_000 + 20 * 1000

    host_q = [o for o in outs if o.type == "question_start" and o.target == "host"][0].payload
    players_q = [o for o in outs if o.type == "question_start" and o.target == "players"][0].payload
    assert host_q["correct"] == 1
    assert "correct" not in players_q
    assert players_q["question"] == "Année de Matrix ?"
    assert players_q["choices"] == ["1997", "1999", "2001", "2003"]
    assert players_q["index"] == 0 and players_q["total"] == 2
    assert players_q["ends_at"] == session.question_ends_at


def test_shuffle_choices_permutes_presentation_and_remaps_correct():
    import random

    session, _ = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM, shuffle_choices=True)
    random.seed(42)
    outs = qcm.start_qcm(session, now=0)

    players_q = [o for o in outs if o.type == "question_start" and o.target == "players"][0].payload
    host_q = [o for o in outs if o.type == "question_start" and o.target == "host"][0].payload
    # presented choices are a permutation of the originals
    assert sorted(players_q["choices"]) == sorted(["1997", "1999", "2001", "2003"])
    # host's presented `correct` index points at the original correct value "1999"
    assert players_q["choices"][host_q["correct"]] == "1999"
    assert len(session.presented_order) == 4 and sorted(session.presented_order) == [0, 1, 2, 3]


def test_answer_submit_records_once_and_broadcasts_progress():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)

    outs = qcm.answer_submit(session, alice.id, choice=1, now=2_000)
    assert session.answers[alice.id].choice == 1
    assert session.answers[alice.id].ts == 2_000
    progress = [o for o in outs if o.type == "qcm_progress"][0].payload
    assert progress == {"answered": 1, "total": 2}
    ack = [o for o in outs if o.type == "answer_ack"]
    assert ack and ack[0].target == alice.id

    # second answer from same player is ignored
    assert qcm.answer_submit(session, alice.id, choice=2, now=3_000) == []
    assert session.answers[alice.id].choice == 1
    assert not qcm.all_answered(session)  # bob hasn't answered

    qcm.answer_submit(session, bob.id, choice=0, now=2_500)
    assert qcm.all_answered(session)


def test_answer_submit_ignored_outside_question_active():
    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)  # still LOBBY
    assert qcm.answer_submit(session, alice.id, choice=0, now=1) == []


def test_all_answered_ignores_disconnected_players():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)
    bob.connected = False
    qcm.answer_submit(session, alice.id, choice=1, now=1_000)
    assert qcm.all_answered(session)  # bob disconnected → doesn't block


def test_speed_factor_bounds():
    assert qcm._speed_factor(0, 20) == 1.0
    assert qcm._speed_factor(20, 20) == 0.5
    assert abs(qcm._speed_factor(4, 20) - 0.9) < 1e-9
    assert qcm._speed_factor(999, 20) == 0.5  # clamped


def test_streak_multiplier_caps_at_50_percent():
    assert qcm._streak_mult(1) == 1.0
    assert abs(qcm._streak_mult(2) - 1.10) < 1e-9
    assert abs(qcm._streak_mult(6) - 1.50) < 1e-9
    assert qcm._streak_mult(20) == 1.5  # capped


def test_reveal_awards_speed_times_streak_and_builds_distribution():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    qcm.set_qcm_rounds(session, _TWO_QCM)  # Q0 correct index 1
    qcm.start_qcm(session, now=0)
    alice.streak = 2  # so a correct answer makes streak_after = 3 → mult 1.20
    qcm.answer_submit(session, alice.id, choice=1, now=4_000)  # correct, t=4s, f=0.9
    qcm.answer_submit(session, bob.id, choice=0, now=5_000)  # wrong

    outs = qcm.reveal(session)
    assert session.state is GameState.REVEAL
    assert alice.score == round(1000 * 0.9 * 1.20)  # 1080
    assert alice.streak == 3
    assert bob.score == 0
    assert bob.streak == 0  # wrong answer resets

    payload = [o for o in outs if o.type == "reveal"][0].payload
    assert payload["correct"] == 1
    assert payload["distribution"] == [1, 1, 0, 0]  # choice0:bob, choice1:alice
    assert payload["deltas"][alice.id] == 1080


def test_bonus_question_doubles_base_points():
    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, [{**_TWO_QCM[0], "bonus": True}])
    qcm.start_qcm(session, now=0)
    alice.streak = 2  # mult 1.20 after a correct answer
    qcm.answer_submit(session, alice.id, choice=_TWO_QCM[0]["correct"], now=4_000)  # f=0.9
    qcm.reveal(session)
    assert alice.score == round(1000 * 2 * 0.9 * 1.20)  # base doubled by bonus → 2160


def test_no_answer_resets_streak():
    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)
    alice.streak = 4
    qcm.reveal(session)  # alice never answered
    assert alice.streak == 0
    assert alice.score == 0


def test_skip_reveals_without_awarding():
    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)
    alice.streak = 2
    qcm.answer_submit(session, alice.id, choice=1, now=1_000)  # correct
    qcm.reveal(session, award=False)
    assert alice.score == 0  # skipped → no points
    assert alice.streak == 2  # unchanged
    assert session.state is GameState.REVEAL


def test_reveal_with_shuffled_choices_scores_against_original_correct():
    import random

    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM, shuffle_choices=True)
    random.seed(7)
    outs = qcm.start_qcm(session, now=0)
    host_q = [o for o in outs if o.type == "question_start" and o.target == "host"][0].payload
    presented_correct = host_q["correct"]  # presented index of "1999"
    qcm.answer_submit(session, alice.id, choice=presented_correct, now=1_000)
    qcm.reveal(session)
    assert alice.score > 0  # answering the presented-correct choice scores


def test_to_scoreboard_computes_rank_deltas():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)
    alice.last_rank, bob.last_rank = 2, 1  # bob was ahead
    alice.score, bob.score = 100, 50  # now alice leads
    session.state = GameState.REVEAL

    outs = qcm.to_scoreboard(session)
    assert session.state is GameState.SCOREBOARD
    board = [o for o in outs if o.type == "scoreboard"][0].payload["players"]
    by_pseudo = {p["pseudo"]: p for p in board}
    assert by_pseudo["Alice"]["rank"] == 1 and by_pseudo["Alice"]["delta"] == 1  # 2 → 1, up
    assert by_pseudo["Bob"]["rank"] == 2 and by_pseudo["Bob"]["delta"] == -1
    assert alice.last_rank == 1 and bob.last_rank == 2  # stored for next time


def test_next_advances_to_next_question_then_game_end():
    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)  # Q0
    session.state = GameState.SCOREBOARD

    qcm.next_(session, now=10_000)  # → Q1
    assert session.state is GameState.QUESTION_ACTIVE
    assert session.qcm_index == 1

    qcm.reveal(session)
    qcm.to_scoreboard(session)
    outs = qcm.next_(session, now=20_000)  # no more questions → GAME_END
    assert session.state is GameState.GAME_END
    assert [o for o in outs if o.type == "game_end"]


def test_game_end_podium_top_three_with_ties():
    session, [a, b, c, d] = _session_with_players("A", "B", "C", "D")
    a.score, b.score, c.score, d.score = 30, 30, 20, 10
    payload = qcm.game_end_payload(session)
    podium = payload["podium"]
    assert [p["rank"] for p in podium[:2]] == [1, 1]  # tie at top
    assert len(podium) <= 4  # top scores incl. ties, capped reasonably


def test_state_sync_payload_restores_my_choice_on_reconnect():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    qcm.start_qcm(session, now=0)

    # Alice answers, Bob has not answered yet.
    qcm.answer_submit(session, alice.id, choice=1, now=2_000)

    # Reconnecting player who has answered: my_choice should be their submitted choice.
    alice_sync = qcm.state_sync_payload(session, role="player", player_id=alice.id)
    assert alice_sync["my_choice"] == 1

    # Reconnecting player who has NOT answered: my_choice should be None.
    bob_sync = qcm.state_sync_payload(session, role="player", player_id=bob.id)
    assert bob_sync["my_choice"] is None

    # TV role (no player_id): my_choice must not leak another player's answer.
    tv_sync = qcm.state_sync_payload(session, role="tv")
    assert tv_sync["my_choice"] is None


def test_question_start_includes_image_for_host_and_players():
    session, _ = _session_with_players("Alice")
    qcm.set_qcm_rounds(
        session,
        [{"question": "q", "choices": ["a", "b", "c", "d"], "correct": 0, "image": "/media/x.webp"}],
    )
    outs = qcm.start_qcm(session, now=0)
    host = [o for o in outs if o.type == "question_start" and o.target == "host"][0]
    players = [o for o in outs if o.type == "question_start" and o.target == "players"][0]
    assert host.payload["image"] == "/media/x.webp"
    assert players.payload["image"] == "/media/x.webp"


def test_prepared_qcm_includes_image_host_only():
    session, _ = _session_with_players("Alice")
    outs = qcm.set_qcm_rounds(
        session,
        [{"question": "q", "choices": ["a", "b", "c", "d"], "correct": 0, "image": "/media/x.webp"}],
    )
    prep = [o for o in outs if o.type == "prepared_qcm"][0]
    assert prep.target == "host"
    assert prep.payload["rounds"][0]["image"] == "/media/x.webp"


def test_replay_game_resets_scores_and_restarts():
    session, [alice] = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    alice.score = 7
    session.state = GameState.GAME_END
    outs = qcm.replay_game(session, now=0)
    assert alice.score == 0
    assert session.state is GameState.QUESTION_ACTIVE
    assert session.qcm_index == 0
    assert _by_type(outs, "player_list")
    assert _by_type(outs, "question_start")


def test_replay_game_noop_outside_game_end():
    session, _ = _session_with_players("Alice")
    qcm.set_qcm_rounds(session, _TWO_QCM)
    assert qcm.replay_game(session, now=0) == []
