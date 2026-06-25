"""Unit tests for the pure Blindtest engine (Phase 3, cahier Â§16).

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from game import blindtest, engine
from game.models import GameMode, GameState
from game.store import SessionStore

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _by_type(outs, type_):
    return [o for o in outs if o.type == type_]


def _by_target(outs, target):
    return [o for o in outs if o.target == target]


def _session_with_players(*pseudos):
    store = SessionStore()
    session = store.create()
    players = [engine.join(session, p)[0] for p in pseudos]
    return session, players


_TWO_TRACKS = [
    {
        "spotify_track_id": "abc123",
        "uri": "spotify:track:abc123",
        "title": "Thriller",
        "artist": "Michael Jackson",
        "cover_url": "https://example.com/thriller.jpg",
        "duration_ms": 240000,
        "start_ms": 5000,
        "points_title": 2,
        "points_artist": 1,
    },
    {
        "spotify_track_id": "def456",
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "points_title": 1,
        "points_artist": 1,
    },
]


# --------------------------------------------------------------------------- #
# set_blindtest_tracks
# --------------------------------------------------------------------------- #


def test_set_blindtest_tracks_sets_mode_and_stores_tracks():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)

    assert session.mode is GameMode.BLINDTEST
    assert len(session.blindtest_tracks) == 2
    assert session.bt_index == -1
    assert session.state is GameState.LOBBY

    t0 = session.blindtest_tracks[0]
    assert t0.spotify_track_id == "abc123"
    assert t0.title == "Thriller"
    assert t0.artist == "Michael Jackson"
    assert t0.points_title == 2
    assert t0.points_artist == 1

    # second track: uri auto-generated, defaults filled
    t1 = session.blindtest_tracks[1]
    assert t1.spotify_track_id == "def456"
    assert t1.uri == "spotify:track:def456"
    assert t1.cover_url == ""
    assert t1.duration_ms == 0
    assert t1.start_ms == 0


def test_set_blindtest_tracks_prepared_blindtest_is_host_only_and_carries_track_info():
    session, _ = _session_with_players()
    outs = blindtest.set_blindtest_tracks(session, _TWO_TRACKS)

    prepared = _by_type(outs, "prepared_blindtest")
    assert prepared, "expected a prepared_blindtest outbound"
    assert all(o.target == "host" for o in prepared), "prepared_blindtest must only target host"

    payload = prepared[0].payload
    assert payload["index"] == -1
    tracks = payload["tracks"]
    assert len(tracks) == 2
    assert tracks[0]["title"] == "Thriller"
    assert tracks[0]["artist"] == "Michael Jackson"
    assert tracks[0]["uri"] == "spotify:track:abc123"
    # never broadcast prepared_blindtest to players/all
    assert not [o for o in outs if o.type == "prepared_blindtest" and o.target not in ("host",)]


def test_set_blindtest_tracks_rejected_outside_lobby():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    session.state = GameState.BUZZER_OPEN
    result = blindtest.set_blindtest_tracks(session, _TWO_TRACKS[:1])
    assert result == []
    assert len(session.blindtest_tracks) == 2  # unchanged


# --------------------------------------------------------------------------- #
# start_blindtest / load_track
# --------------------------------------------------------------------------- #


def test_start_blindtest_opens_first_track_and_sets_buzzer_open():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.start_blindtest(session, now=0)

    assert session.state is GameState.BUZZER_OPEN
    assert session.bt_index == 0


def test_start_blindtest_resets_streaks():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    alice.streak, bob.streak = 3, 5
    alice.last_rank, bob.last_rank = 1, 2
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.start_blindtest(session, now=0)

    assert alice.streak == 0
    assert bob.streak == 0
    assert alice.last_rank == 0
    assert bob.last_rank == 0


def test_start_blindtest_rejected_if_no_tracks():
    session, _ = _session_with_players()
    assert blindtest.start_blindtest(session, now=0) == []


def test_start_blindtest_rejected_outside_lobby():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    session.state = GameState.BUZZER_OPEN
    assert blindtest.start_blindtest(session, now=0) == []


def test_load_track_host_payload_includes_track_and_audio_play():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    outs = blindtest.load_track(session, 0, 0)

    host_outs = [o for o in outs if o.type == "bt_track" and o.target == "host"]
    assert host_outs, "host must receive bt_track"
    payload = host_outs[0].payload
    assert payload["audio"] == "start"
    assert payload["title"] == "Thriller"
    assert payload["artist"] == "Michael Jackson"
    assert payload["uri"] == "spotify:track:abc123"
    assert payload["index"] == 0
    assert payload["total"] == 2


def test_load_track_players_payload_has_no_track_secrets():
    """Â§16: players must NOT receive title/artist/uri/cover_url before REVEAL."""
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    outs = blindtest.load_track(session, 0, 0)

    players_outs = [o for o in outs if o.type == "bt_track" and o.target == "players"]
    assert players_outs, "players must receive bt_track"
    payload = players_outs[0].payload
    assert "title" not in payload
    assert "artist" not in payload
    assert "uri" not in payload
    assert "cover_url" not in payload
    assert payload["index"] == 0
    assert payload["total"] == 2


def test_load_track_out_of_bounds_returns_empty():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    assert blindtest.load_track(session, -1, 0) == []
    assert blindtest.load_track(session, 2, 0) == []


def test_load_track_resets_buzz_fields():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    # simulate a prior buzz state
    session.buzz_queue = [object()]  # type: ignore[list-item]
    session.buzzed_ids = {alice.id}
    session.floor_index = 1
    session.bt_title_by = alice.id
    session.bt_artist_by = alice.id

    blindtest.load_track(session, 0, 0)
    assert session.buzz_queue == []
    assert session.buzzed_ids == set()
    assert session.floor_index == 0
    assert session.bt_title_by is None
    assert session.bt_artist_by is None


def test_load_track_emits_buzz_locked_resetting_clients():
    """load_track must broadcast a fresh buzz_locked so every client (host
    BuzzStrip + player/tv) clears the previous track's queue/floor (no
    round_state is emitted in blindtest mode)."""
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    outs = blindtest.load_track(session, 0, 0)

    buzz_outs = [o for o in outs if o.type == "buzz_locked"]
    assert buzz_outs, "load_track must emit buzz_locked"
    assert buzz_outs[0].target == "all"
    payload = buzz_outs[0].payload
    assert payload["state"] == GameState.BUZZER_OPEN.value
    assert payload["floor_player_id"] is None
    assert payload["queue"] == []


# --------------------------------------------------------------------------- #
# on_buzz
# --------------------------------------------------------------------------- #


def test_on_buzz_first_buzz_transitions_to_buzzed_and_emits_pause():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    outs = blindtest.on_buzz(session, alice.id, now=5000)
    assert session.state is GameState.BUZZED
    buzz_outs = _by_type(outs, "buzz_locked")
    assert buzz_outs, "expected buzz_locked"
    audio_outs = _by_type(outs, "bt_audio")
    assert audio_outs, "expected bt_audio pause"
    assert audio_outs[0].payload["audio"] == "pause"
    assert audio_outs[0].target == "host"


def test_on_buzz_second_player_queued():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    blindtest.on_buzz(session, alice.id, now=5000)
    outs = blindtest.on_buzz(session, bob.id, now=5100)

    # Bob is queued â€” still BUZZED, floor stays with alice
    assert session.state is GameState.BUZZED
    assert session.floor_player_id == alice.id
    assert len(session.buzz_queue) == 2

    # No new audio pause (floor didn't change), but buzz_locked still comes through
    buzz_outs = _by_type(outs, "buzz_locked")
    assert buzz_outs


def test_on_buzz_idempotent_same_player():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)
    result = blindtest.on_buzz(session, alice.id, now=5100)
    assert result == []
    assert len(session.buzz_queue) == 1


def test_on_buzz_queued_buzz_emits_no_audio_pause():
    """Only the first floor-acquiring buzz pauses; a queued buzz must not."""
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    blindtest.on_buzz(session, alice.id, now=5000)  # alice takes the floor
    outs = blindtest.on_buzz(session, bob.id, now=5100)  # bob queued behind alice

    assert session.floor_player_id == alice.id
    assert _by_type(outs, "bt_audio") == []  # no spurious pause for a queued buzz


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #


def test_validate_title_only_awards_points_title_and_emits_partial():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, points_title=2, points_artist=1)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    outs = blindtest.validate(session, title=True, artist=False)

    assert alice.score == 2  # global points_title
    assert session.bt_title_by == alice.id
    assert session.bt_artist_by is None
    assert session.state is GameState.BUZZED  # NOT yet fully answered

    player_list = _by_type(outs, "player_list")
    assert player_list

    partial = _by_type(outs, "bt_partial")
    assert partial, "expected bt_partial when not fully answered"
    assert partial[0].target == "host"
    assert partial[0].payload["title_by"] == alice.id
    assert partial[0].payload["artist_by"] is None

    # must NOT be auto-revealed
    assert not _by_type(outs, "reveal")


def test_validate_artist_only_awards_points_artist():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    blindtest.validate(session, title=False, artist=True)

    assert alice.score == 1  # points_artist
    assert session.bt_title_by is None
    assert session.bt_artist_by == alice.id
    assert session.state is GameState.BUZZED


def test_validate_both_triggers_auto_reveal():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, points_title=2, points_artist=1)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    outs = blindtest.validate(session, title=True, artist=True)

    assert session.state is GameState.REVEAL
    reveal_outs = _by_type(outs, "reveal")
    assert reveal_outs, "auto-reveal expected"
    payload = reveal_outs[0].payload
    assert payload["title"] == "Thriller"
    assert payload["artist"] == "Michael Jackson"
    assert payload["cover_url"] == "https://example.com/thriller.jpg"
    assert payload["deltas"][alice.id] == 3  # 2 + 1


def test_validate_two_separate_calls_then_auto_reveal():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, points_title=2, points_artist=1)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    blindtest.validate(session, title=True, artist=False)  # alice gets title
    # floor is still alice, state BUZZED
    outs = blindtest.validate(session, title=False, artist=True)  # alice gets artist too

    assert session.state is GameState.REVEAL
    reveal_outs = _by_type(outs, "reveal")
    assert reveal_outs
    payload = reveal_outs[0].payload
    assert payload["deltas"][alice.id] == 3  # both points on same player


def test_validate_idempotent_title_already_found():
    """Calling validate(title=True) a second time must not double-award."""
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    blindtest.validate(session, title=True, artist=False)
    score_after_first = alice.score

    # Validate title again (should not re-award)
    blindtest.validate(session, title=True, artist=False)
    assert alice.score == score_after_first


def test_validate_noop_outside_buzzed():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)  # BUZZER_OPEN, no floor
    assert blindtest.validate(session, title=True, artist=True) == []


def test_validate_neither_title_nor_artist_is_noop():
    """validate(title=False, artist=False) must emit nothing and award nothing."""
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    outs = blindtest.validate(session, title=False, artist=False)
    assert outs == []
    assert alice.score == 0
    assert session.bt_title_by is None
    assert session.bt_artist_by is None
    assert session.state is GameState.BUZZED  # state unchanged


# --------------------------------------------------------------------------- #
# cont
# --------------------------------------------------------------------------- #


def test_cont_reopens_buzzer_after_partial_validate():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)
    blindtest.validate(session, title=True, artist=False)  # partial

    outs = blindtest.cont(session, now=0)

    assert session.state is GameState.BUZZER_OPEN
    assert session.bt_title_by == alice.id  # kept
    assert session.bt_artist_by is None  # kept (was None)
    assert session.buzz_queue == []
    assert session.buzzed_ids == set()

    host_track = [o for o in outs if o.type == "bt_track" and o.target == "host"]
    assert host_track and host_track[0].payload["audio"] == "resume"

    players_track = [o for o in outs if o.type == "bt_track" and o.target == "players"]
    assert players_track
    payload = players_track[0].payload
    assert "title" not in payload
    assert "artist" not in payload
    assert "uri" not in payload


def test_cont_noop_outside_buzzed():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    assert blindtest.cont(session, now=0) == []  # BUZZER_OPEN not BUZZED


# --------------------------------------------------------------------------- #
# invalidate
# --------------------------------------------------------------------------- #


def test_invalidate_passes_floor_to_next_in_queue():
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)
    blindtest.on_buzz(session, bob.id, now=5100)

    outs = blindtest.invalidate(session)

    assert session.state is GameState.BUZZED
    assert session.floor_player_id == bob.id

    # audio stays pause (next player in queue)
    audio_outs = _by_type(outs, "bt_audio")
    assert audio_outs and audio_outs[0].payload["audio"] == "pause"


def test_invalidate_queue_exhausted_reopens_buzzer():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)

    outs = blindtest.invalidate(session)

    assert session.state is GameState.BUZZER_OPEN

    audio_outs = _by_type(outs, "bt_audio")
    assert audio_outs and audio_outs[0].payload["audio"] == "resume"


# --------------------------------------------------------------------------- #
# reveal
# --------------------------------------------------------------------------- #


def test_reveal_sets_state_to_reveal_and_broadcasts_track_info():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, points_title=2, points_artist=1)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)
    blindtest.validate(session, title=True, artist=False)  # alice has title only

    outs = blindtest.reveal(session)

    assert session.state is GameState.REVEAL
    reveal_outs = _by_type(outs, "reveal")
    assert reveal_outs
    payload = reveal_outs[0].payload
    assert payload["title"] == "Thriller"
    assert payload["artist"] == "Michael Jackson"
    assert payload["cover_url"] == "https://example.com/thriller.jpg"
    # only title was won â€” deltas contain only title points
    assert payload["deltas"][alice.id] == 2


def test_reveal_from_buzzer_open_no_winner():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    outs = blindtest.reveal(session)
    assert session.state is GameState.REVEAL
    reveal_outs = _by_type(outs, "reveal")
    assert reveal_outs
    payload = reveal_outs[0].payload
    assert payload["deltas"] == {}


def test_reveal_noop_if_not_in_playing_state():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    # LOBBY state
    assert blindtest.reveal(session) == []


# --------------------------------------------------------------------------- #
# to_scoreboard and next_
# --------------------------------------------------------------------------- #


def test_to_scoreboard_delegates_to_qcm():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    session.state = GameState.REVEAL  # force REVEAL

    outs = blindtest.to_scoreboard(session)
    assert session.state is GameState.SCOREBOARD
    assert _by_type(outs, "scoreboard")


def test_next_advances_to_next_track():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    session.state = GameState.SCOREBOARD

    outs = blindtest.next_(session, now=0)
    assert session.bt_index == 1
    assert session.state is GameState.BUZZER_OPEN

    host_track = [o for o in outs if o.type == "bt_track" and o.target == "host"]
    assert host_track
    assert host_track[0].payload["title"] == "Bohemian Rhapsody"


def test_next_last_track_triggers_game_end():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    # jump to last track then scoreboard
    blindtest.load_track(session, 1, 0)
    session.state = GameState.SCOREBOARD

    outs = blindtest.next_(session, now=0)
    assert session.state is GameState.GAME_END
    game_end = _by_type(outs, "game_end")
    assert game_end
    assert "podium" in game_end[0].payload


def test_next_noop_outside_scoreboard():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)  # BUZZER_OPEN
    assert blindtest.next_(session, now=0) == []


# --------------------------------------------------------------------------- #
# Full progression test
# --------------------------------------------------------------------------- #


def test_full_game_progression():
    """Load â†’ buzz â†’ validate both â†’ reveal â†’ scoreboard â†’ next â†’ game_end."""
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.start_blindtest(session, now=0)  # loads track 0

    # Alice buzzes first (must be after bt_play_started_at = 0 + 3000 = 3000)
    blindtest.on_buzz(session, alice.id, now=5000)
    assert session.state is GameState.BUZZED

    # Host validates both title and artist â†’ auto-reveal
    outs = blindtest.validate(session, title=True, artist=True)
    assert session.state is GameState.REVEAL

    # to_scoreboard
    outs = blindtest.to_scoreboard(session)
    assert session.state is GameState.SCOREBOARD

    # next â†’ track 1
    outs = blindtest.next_(session, now=0)
    assert session.bt_index == 1
    assert session.state is GameState.BUZZER_OPEN

    # Force through track 1 to game_end
    session.state = GameState.REVEAL
    blindtest.to_scoreboard(session)
    outs = blindtest.next_(session, now=0)
    assert session.state is GameState.GAME_END
    assert _by_type(outs, "game_end")


# --------------------------------------------------------------------------- #
# Â§16 regression: no title/artist/uri/cover_url before REVEAL on players/all
# --------------------------------------------------------------------------- #


def test_s16_no_track_secrets_before_reveal():
    """Â§16 regression: none of the payloads targeting 'players' or 'all'
    may contain title/artist/cover_url/uri before the 'reveal' message is sent."""
    session, [alice, bob] = _session_with_players("Alice", "Bob")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)

    forbidden_keys = {"title", "artist", "cover_url", "uri"}

    def _check(outs, label):
        for o in outs:
            if o.target in ("players", "all"):
                leaks = forbidden_keys & o.payload.keys()
                assert not leaks, f"Â§16 violation in {label}: target={o.target!r} type={o.type!r} leaked {leaks}"

    _check(blindtest.set_blindtest_tracks(session, _TWO_TRACKS), "set_blindtest_tracks")
    _check(blindtest.start_blindtest(session, now=0), "start_blindtest")  # includes load_track(0)
    # bt_play_started_at == 3000 (0 + countdown 3000)
    _check(blindtest.on_buzz(session, alice.id, now=5000), "on_buzz alice")
    _check(blindtest.on_buzz(session, bob.id, now=5100), "on_buzz bob")
    _check(blindtest.validate(session, title=True, artist=False), "validate title-only")
    _check(blindtest.cont(session, now=0), "cont")
    _check(blindtest.on_buzz(session, alice.id, now=100), "on_buzz alice (after cont, now=100 >= started_at=0)")

    # reveal is the point where track info IS allowed to go to all â€” we stop checking here
    reveal_outs = blindtest.reveal(session)
    # After reveal it's fine, but let's check the reveal payload itself has the info
    assert any(o.target == "all" and o.type == "reveal" for o in reveal_outs)


# --------------------------------------------------------------------------- #
# state_sync_payload
# --------------------------------------------------------------------------- #


def test_state_sync_payload_player_during_buzzer_open_no_track_secrets():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    data = blindtest.state_sync_payload(session, role="player", player_id=alice.id)
    assert data["mode"] == "blindtest"
    assert data["state"] == "BUZZER_OPEN"
    assert data["index"] == 0
    assert data["total"] == 2
    assert "title" not in data
    assert "artist" not in data
    assert "uri" not in data
    assert "cover_url" not in data


def test_state_sync_payload_host_during_buzzer_open_includes_track_and_audio():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    data = blindtest.state_sync_payload(session, role="host")
    assert data["title"] == "Thriller"
    assert data["artist"] == "Michael Jackson"
    assert data["uri"] == "spotify:track:abc123"
    assert data["audio"] == "resume"  # BUZZER_OPEN + playing → resume on reconnect


def test_state_sync_payload_host_during_buzzed_audio_is_pause():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)  # after bt_play_started_at (0+3000)

    data = blindtest.state_sync_payload(session, role="host")
    assert data["audio"] == "pause"


def test_state_sync_payload_reveal_state_includes_track_for_all():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)  # after bt_play_started_at (0+3000)
    blindtest.reveal(session)  # state â†’ REVEAL

    for role in ("host", "player", "tv"):
        data = blindtest.state_sync_payload(session, role=role, player_id=alice.id if role == "player" else None)
        assert "reveal" in data
        assert data["reveal"]["title"] == "Thriller"


def test_state_sync_payload_game_end():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 1, 0)
    session.state = GameState.SCOREBOARD
    blindtest.next_(session, now=0)  # â†’ GAME_END

    data = blindtest.state_sync_payload(session, role="player", player_id=alice.id)
    assert data["state"] == "GAME_END"
    assert "game_end" in data
    assert "podium" in data["game_end"]


def test_state_sync_payload_tv_during_buzzer_open_no_track_secrets():
    session, _ = _session_with_players()
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)

    data = blindtest.state_sync_payload(session, role="tv")
    assert "title" not in data
    assert "artist" not in data
    assert "uri" not in data
    assert data["index"] == 0


# --------------------------------------------------------------------------- #
# Timing config (Blindtest v2 â€” Task 1)
# --------------------------------------------------------------------------- #


def test_set_blindtest_tracks_stores_config():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=15, random_start=True, countdown=False)
    assert session.bt_max_play_ms == 15000
    assert session.bt_random_start is True
    assert session.bt_countdown_ms == 0


def test_set_blindtest_tracks_config_defaults():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    assert session.bt_max_play_ms == 30000
    assert session.bt_countdown_ms == 3000
    assert session.bt_random_start is False


# --------------------------------------------------------------------------- #
# Timing payload + countdown + buzz gate (Blindtest v2 â€” Task 2)
# --------------------------------------------------------------------------- #


def test_countdown_sets_started_and_ends_at():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10, countdown=True)
    blindtest.start_blindtest(session, now=1000)
    assert session.bt_play_started_at == 1000 + 3000
    assert session.bt_play_ends_at == session.bt_play_started_at + 10000


def test_no_cap_means_ends_at_zero():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=0)
    blindtest.start_blindtest(session, now=0)
    assert session.bt_play_ends_at == 0


def test_buzz_rejected_during_countdown():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=True)
    blindtest.start_blindtest(session, now=1000)  # started_at == 4000
    assert blindtest.on_buzz(session, alice.id, now=2000) == []
    outs = blindtest.on_buzz(session, alice.id, now=5000)
    assert any(o.type == "buzz_locked" for o in outs)


def test_bt_track_payload_has_timing_and_no_secrets_for_players():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10)
    outs = blindtest.start_blindtest(session, now=0)
    players = [o for o in outs if o.type == "bt_track" and o.target == "players"][0]
    assert players.payload["max_play_ms"] == 10000
    assert "starts_at" in players.payload and "ends_at" in players.payload
    assert "title" not in players.payload and "start_ms" not in players.payload
    host = [o for o in outs if o.type == "bt_track" and o.target == "host"][0]
    assert "start_ms" in host.payload and host.payload["max_play_ms"] == 10000


def test_random_start_within_bounds():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10, random_start=True)
    blindtest.load_track(session, 0, 0)
    assert 0 <= session.bt_current_start_ms <= 240000 - 10000


# --------------------------------------------------------------------------- #
# Task 3: reveal/scoreboard pause + on_play_timeout + replay
# --------------------------------------------------------------------------- #


def test_reveal_pauses_audio():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=False)
    blindtest.start_blindtest(session, now=0)
    blindtest.on_buzz(session, alice.id, now=10)
    outs = blindtest.validate(session, title=True, artist=True)  # auto-reveal
    assert any(o.type == "bt_audio" and o.payload["audio"] == "pause" for o in outs)


def test_to_scoreboard_pauses_audio():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=False)
    blindtest.start_blindtest(session, now=0)
    outs = blindtest.to_scoreboard(session)
    assert any(o.type == "bt_audio" and o.payload["audio"] == "pause" for o in outs)


def test_on_play_timeout_pauses_when_open_and_unbuzzed():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=5, countdown=False)
    blindtest.start_blindtest(session, now=0)
    assert [o.payload["audio"] for o in blindtest.on_play_timeout(session) if o.type == "bt_audio"] == ["pause"]


def test_on_play_timeout_noop_when_buzzed():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=False)
    blindtest.start_blindtest(session, now=0)
    blindtest.on_buzz(session, alice.id, now=10)  # floor held → BUZZED
    assert blindtest.on_play_timeout(session) == []


def test_replay_resets_timing_and_emits_play():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=8, countdown=False)
    blindtest.start_blindtest(session, now=0)
    outs = blindtest.replay(session, now=20000)
    assert session.bt_play_started_at == 20000
    assert session.bt_play_ends_at == 28000
    host = [o for o in outs if o.type == "bt_track" and o.target == "host"][0]
    assert host.payload["audio"] == "start"


# --------------------------------------------------------------------------- #
# Pause-aware, clock-skew-safe timing model (Boucan overhaul)
# --------------------------------------------------------------------------- #


def test_timing_block_present_for_all_roles():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10, countdown=False)
    outs = blindtest.start_blindtest(session, now=1000)
    for target in ("host", "players"):
        p = [o for o in outs if o.type == "bt_track" and o.target == target][0].payload
        assert p["server_now"] == 1000
        assert p["seg_started_at"] == 1000
        assert p["played_ms"] == 0
        assert p["playing"] is True
        assert "audio_seq" in p


def test_buzz_freezes_played_ms_and_pauses():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=30, countdown=False)
    blindtest.start_blindtest(session, now=0)  # seg starts at 0, playing
    outs = blindtest.on_buzz(session, alice.id, now=7000)  # 7s consumed
    assert session.bt_playing is False
    assert session.bt_played_ms == 7000
    # players get a frozen timing update (no secrets), so their bar stops too
    players = [o for o in outs if o.type == "bt_track" and o.target == "players"]
    assert players and players[0].payload["playing"] is False
    assert players[0].payload["played_ms"] == 7000
    assert "title" not in players[0].payload


def test_cont_resumes_and_keeps_played_ms():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=30, countdown=False)
    blindtest.start_blindtest(session, now=0)
    blindtest.on_buzz(session, alice.id, now=8000)  # 8s played, frozen
    blindtest.validate(session, title=True, artist=False, now=8000)  # partial
    outs = blindtest.cont(session, now=20000)
    assert session.bt_playing is True
    assert session.bt_played_ms == 8000  # kept across the pause
    assert session.bt_play_started_at == 20000  # segment restarts now
    assert session.bt_play_ends_at == 20000 + (30000 - 8000)  # remaining budget
    host = [o for o in outs if o.type == "bt_track" and o.target == "host"][0]
    assert host.payload["audio"] == "resume"


def test_pause_then_resume_accumulates_played_ms():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=30, countdown=False)
    blindtest.start_blindtest(session, now=0)
    outs = blindtest.pause_bt(session, now=5000)
    assert session.bt_playing is False
    assert session.bt_played_ms == 5000
    assert any(o.type == "bt_audio" and o.payload["audio"] == "pause" for o in outs)
    # resume later: a second pause adds to the first
    outs = blindtest.resume_bt(session, now=10000)
    assert session.bt_playing is True
    assert session.bt_play_started_at == 10000
    assert any(o.type == "bt_audio" and o.payload["audio"] == "resume" for o in outs)
    blindtest.pause_bt(session, now=13000)  # +3s
    assert session.bt_played_ms == 8000


def test_pause_bt_noop_when_already_paused():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=False)
    blindtest.start_blindtest(session, now=0)
    blindtest.on_buzz(session, alice.id, now=1000)  # BUZZED, not BUZZER_OPEN
    assert blindtest.pause_bt(session, now=2000) == []


def test_replay_resets_played_ms_to_zero():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=30, countdown=False)
    blindtest.start_blindtest(session, now=0)
    blindtest.pause_bt(session, now=9000)  # 9s consumed
    outs = blindtest.replay(session, now=20000)
    assert session.bt_played_ms == 0
    assert session.bt_playing is True
    host = [o for o in outs if o.type == "bt_track" and o.target == "host"][0]
    assert host.payload["audio"] == "start"


def test_global_points_applied_to_all_songs():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, points_title=3, points_artist=2)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)
    blindtest.validate(session, title=True, artist=True, now=5000)
    assert alice.score == 5  # 3 + 2 from globals, ignoring per-track values


def test_bonus_song_doubles_points():
    session, [alice] = _session_with_players("Alice")
    tracks = [{**_TWO_TRACKS[0], "bonus": True}]
    blindtest.set_blindtest_tracks(session, tracks, points_title=3, points_artist=2)
    blindtest.load_track(session, 0, 0)
    blindtest.on_buzz(session, alice.id, now=5000)
    outs = blindtest.validate(session, title=True, artist=True, now=5000)
    assert alice.score == 10  # (3 + 2) * 2
    reveal_out = [o for o in outs if o.type == "reveal"][0]
    assert reveal_out.payload["deltas"][alice.id] == 10


def test_bonus_flag_broadcast_to_all_clients():
    session, _ = _session_with_players("Alice")
    tracks = [{**_TWO_TRACKS[0], "bonus": True}]
    blindtest.set_blindtest_tracks(session, tracks, countdown=False)
    outs = blindtest.start_blindtest(session, now=0)
    players = [o for o in outs if o.type == "bt_track" and o.target == "players"][0]
    assert players.payload["bonus"] is True  # non-secret: players see ×2


def test_mark_started_reanchors_play_window_to_real_start():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=30, countdown=True)
    blindtest.start_blindtest(session, now=1000)  # seg_started_at = 4000 (countdown)
    seq_before = session.bt_audio_seq
    outs = blindtest.mark_started(session, now=4200)  # audio actually began at 4200
    assert session.bt_play_started_at == 4200
    assert session.bt_play_ends_at == 4200 + 30000  # full window from real start
    assert session.bt_audio_seq == seq_before  # no re-fire of the host audio effect
    host = [o for o in outs if o.type == "bt_track" and o.target == "host"][0]
    assert "audio" not in host.payload


def test_mark_started_noop_when_paused():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=False)
    blindtest.start_blindtest(session, now=0)
    blindtest.pause_bt(session, now=1000)
    assert blindtest.mark_started(session, now=2000) == []


def test_replay_game_resets_scores_and_restarts():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=False)
    alice.score = 5
    session.state = GameState.GAME_END
    outs = blindtest.replay_game(session, now=0)
    assert alice.score == 0
    assert session.state is GameState.BUZZER_OPEN
    assert session.bt_index == 0
    assert any(o.type == "player_list" for o in outs)
    assert any(o.type == "bt_track" for o in outs)


def test_replay_game_noop_outside_game_end():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.load_track(session, 0, 0)
    assert blindtest.replay_game(session, now=0) == []


def test_audio_seq_increments_on_each_transition():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=30, countdown=False)
    blindtest.start_blindtest(session, now=0)
    seqs = [session.bt_audio_seq]
    blindtest.pause_bt(session, now=2000)
    seqs.append(session.bt_audio_seq)
    blindtest.resume_bt(session, now=3000)
    seqs.append(session.bt_audio_seq)
    blindtest.replay(session, now=4000)
    seqs.append(session.bt_audio_seq)
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)  # strictly increasing
