"""Integration test of the WebSocket wiring via Starlette's TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def _read_until(ws, type_, limit=12, where=None):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == type_ and (where is None or where(msg["payload"])):
            return msg
    raise AssertionError(f"message {type_!r} not received")


def test_full_buzzer_flow():
    client = TestClient(app)
    created = client.post("/api/sessions").json()
    code, secret = created["code"], created["host_secret"]

    with (
        client.websocket_connect("/ws") as host,
        client.websocket_connect("/ws") as player,
    ):
        host.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": secret}})
        host_sync = _read_until(host, "state_sync")
        assert host_sync["payload"]["round"]["state"] == "LOBBY"

        player.send_json({"type": "join", "payload": {"code": code, "role": "player", "pseudo": "Alice"}})
        player_sync = _read_until(player, "state_sync")
        player_id = player_sync["payload"]["you"]["id"]
        assert player_sync["payload"]["you"]["reconnect_token"]

        # Host opens the buzzer with a secret answer
        host.send_json(
            {
                "type": "host_action",
                "payload": {"action": "open_buzzer", "question_text": "1+1 ?", "answer": "2", "points": 5},
            }
        )
        player_round = _read_until(player, "round_state")
        assert player_round["payload"]["state"] == "BUZZER_OPEN"
        assert player_round["payload"]["answer"] is None  # hidden from players (§16)

        # Player buzzes
        player.send_json({"type": "buzz", "payload": {}})
        locked = _read_until(host, "buzz_locked", where=lambda p: p["floor_player_id"] is not None)
        assert locked["payload"]["floor_player_id"] == player_id

        # Host validates → points awarded + answer revealed
        host.send_json({"type": "host_action", "payload": {"action": "validate"}})
        reveal = _read_until(player, "reveal")
        assert reveal["payload"]["answer"] == "2"
        plist = _read_until(host, "player_list")
        alice = next(p for p in plist["payload"]["players"] if p["id"] == player_id)
        assert alice["score"] == 5


def test_tv_sees_question_but_never_the_answer():
    client = TestClient(app)
    created = client.post("/api/sessions").json()
    code, secret = created["code"], created["host_secret"]

    with (
        client.websocket_connect("/ws") as host,
        client.websocket_connect("/ws") as tv,
    ):
        host.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": secret}})
        _read_until(host, "state_sync")

        # TV joins with no secret and no pseudo
        tv.send_json({"type": "join", "payload": {"code": code, "role": "tv"}})
        tv_sync = _read_until(tv, "state_sync")
        assert tv_sync["payload"]["you"]["role"] == "tv"

        # Host opens a round carrying a secret answer
        host.send_json(
            {
                "type": "host_action",
                "payload": {"action": "open_buzzer", "question_text": "Capitale ?", "answer": "Paris", "points": 1},
            }
        )
        tv_round = _read_until(tv, "round_state")
        assert tv_round["payload"]["question_text"] == "Capitale ?"
        assert tv_round["payload"]["answer"] is None  # never leaked to the TV (§16)

        # Even after the host has the answer, the TV still doesn't — until reveal
        host.send_json({"type": "host_action", "payload": {"action": "reveal"}})
        tv_reveal = _read_until(tv, "reveal")
        assert tv_reveal["payload"]["answer"] == "Paris"


def test_prepared_list_flow_advances_rounds():
    client = TestClient(app)
    created = client.post("/api/sessions").json()
    code, secret = created["code"], created["host_secret"]

    with client.websocket_connect("/ws") as host:
        host.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": secret}})
        _read_until(host, "state_sync")

        rounds = [
            {"question_text": "Q1", "answer": "A1", "points": 1},
            {"question_text": "Q2", "answer": "A2", "points": 2},
        ]
        host.send_json({"type": "host_action", "payload": {"action": "set_rounds", "rounds": rounds}})
        prepared = _read_until(host, "prepared_rounds")
        assert [r["answer"] for r in prepared["payload"]["rounds"]] == ["A1", "A2"]

        host.send_json({"type": "host_action", "payload": {"action": "start_game"}})
        r0 = _read_until(host, "round_state", where=lambda p: p["state"] == "BUZZER_OPEN")
        assert r0["payload"]["question_text"] == "Q1"
        assert r0["payload"]["round_index"] == 0
        assert r0["payload"]["round_total"] == 2

        host.send_json({"type": "host_action", "payload": {"action": "next"}})
        r1 = _read_until(host, "round_state", where=lambda p: p.get("question_text") == "Q2")
        assert r1["payload"]["round_index"] == 1
        assert r1["payload"]["answer"] == "A2"  # host sees the answer


def test_host_secret_required():
    client = TestClient(app)
    code = client.post("/api/sessions").json()["code"]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": "wrong"}})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["payload"]["code"] == "bad_secret"


def test_qcm_flow_question_answer_reveal_scoreboard():
    client = TestClient(app)
    created = client.post("/api/sessions").json()
    code, secret = created["code"], created["host_secret"]

    with (
        client.websocket_connect("/ws") as host,
        client.websocket_connect("/ws") as tv,
        client.websocket_connect("/ws") as player,
    ):
        host.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": secret}})
        _read_until(host, "state_sync")
        tv.send_json({"type": "join", "payload": {"code": code, "role": "tv"}})
        _read_until(tv, "state_sync")
        player.send_json({"type": "join", "payload": {"code": code, "role": "player", "pseudo": "Alice"}})
        pid = _read_until(player, "state_sync")["payload"]["you"]["id"]

        rounds = [
            {"question": "2+2 ?", "choices": ["3", "4", "5", "6"], "correct": 1, "time_limit": 30, "points": 1000}
        ]
        host.send_json({"type": "host_action", "payload": {"action": "set_qcm_rounds", "rounds": rounds}})
        prepared = _read_until(host, "prepared_qcm")
        assert prepared["payload"]["rounds"][0]["correct"] == 1

        host.send_json({"type": "host_action", "payload": {"action": "start_qcm"}})
        # TV gets the question but never the correct answer
        tv_q = _read_until(tv, "question_start")
        assert tv_q["payload"]["question"] == "2+2 ?"
        assert "correct" not in tv_q["payload"]

        player.send_json({"type": "answer_submit", "payload": {"choice": 1}})
        _read_until(player, "answer_ack")

        # all (1) connected players answered → auto reveal
        rev = _read_until(tv, "reveal")
        assert rev["payload"]["correct"] == 1
        plist = _read_until(
            host, "player_list", where=lambda p: any(x["id"] == pid and x["score"] > 0 for x in p["players"])
        )
        assert next(x for x in plist["payload"]["players"] if x["id"] == pid)["score"] > 0

        host.send_json({"type": "host_action", "payload": {"action": "next"}})  # → scoreboard
        board = _read_until(tv, "scoreboard")
        assert board["payload"]["players"][0]["id"] == pid

        host.send_json({"type": "host_action", "payload": {"action": "next"}})  # → game_end
        end = _read_until(tv, "game_end")
        assert end["payload"]["podium"][0]["id"] == pid


def test_blindtest_flow():
    """Integration test for the blindtest WS wiring (Phase 3, cahier §16)."""
    client = TestClient(app)
    created = client.post("/api/sessions").json()
    code, secret = created["code"], created["host_secret"]

    tracks = [
        {
            "spotify_track_id": "track1",
            "uri": "spotify:track:track1",
            "title": "Song One",
            "artist": "Artist A",
            "cover_url": "https://example.com/cover1.jpg",
            "duration_ms": 30000,
            "start_ms": 0,
            "points_title": 1,
            "points_artist": 1,
        },
        {
            "spotify_track_id": "track2",
            "uri": "spotify:track:track2",
            "title": "Song Two",
            "artist": "Artist B",
            "cover_url": "https://example.com/cover2.jpg",
            "duration_ms": 30000,
            "start_ms": 0,
            "points_title": 1,
            "points_artist": 1,
        },
    ]

    with (
        client.websocket_connect("/ws") as host,
        client.websocket_connect("/ws") as tv,
        client.websocket_connect("/ws") as player,
    ):
        # --- Join ---
        host.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": secret}})
        _read_until(host, "state_sync")

        tv.send_json({"type": "join", "payload": {"code": code, "role": "tv"}})
        _read_until(tv, "state_sync")

        player.send_json({"type": "join", "payload": {"code": code, "role": "player", "pseudo": "Alice"}})
        pid = _read_until(player, "state_sync")["payload"]["you"]["id"]

        # Host: player_list broadcast arrives to host when Alice joins
        _read_until(host, "player_list")

        # --- set_blindtest_tracks (countdown=False so buzz isn't gated in this integration test) ---
        host.send_json(
            {
                "type": "host_action",
                "payload": {"action": "set_blindtest_tracks", "tracks": tracks, "countdown": False},
            }
        )
        prep = _read_until(host, "prepared_blindtest")
        assert len(prep["payload"]["tracks"]) == 2
        assert prep["payload"]["tracks"][0]["title"] == "Song One"
        # player_list broadcast on mode switch
        _read_until(host, "player_list")

        # --- start_blindtest ---
        host.send_json({"type": "host_action", "payload": {"action": "start_blindtest"}})

        # Host receives bt_track WITH uri/title/artist and audio:start
        host_bt = _read_until(host, "bt_track")
        assert host_bt["payload"]["audio"] == "start"
        assert host_bt["payload"]["uri"] == "spotify:track:track1"
        assert host_bt["payload"]["title"] == "Song One"
        assert host_bt["payload"]["artist"] == "Artist A"

        # Player receives bt_track WITHOUT title/artist/uri/cover_url (§16)
        player_bt = _read_until(player, "bt_track")
        assert "title" not in player_bt["payload"]
        assert "artist" not in player_bt["payload"]
        assert "uri" not in player_bt["payload"]
        assert "cover_url" not in player_bt["payload"]

        # TV receives bt_track WITHOUT title/artist/uri/cover_url (§16)
        tv_bt = _read_until(tv, "bt_track")
        assert "title" not in tv_bt["payload"]
        assert "artist" not in tv_bt["payload"]
        assert "uri" not in tv_bt["payload"]
        assert "cover_url" not in tv_bt["payload"]

        # --- player buzz ---
        player.send_json({"type": "buzz", "payload": {}})

        # on_buzz emits: buzz_locked (all) then bt_audio (host)
        buzz_locked = _read_until(host, "buzz_locked")
        assert buzz_locked["payload"]["floor_player_id"] == pid
        bt_audio = _read_until(host, "bt_audio")
        assert bt_audio["payload"]["audio"] == "pause"

        # Player receives buzz_locked (their own lock confirmation)
        _read_until(player, "buzz_locked")

        # --- validate_bt title + artist → auto-reveal ---
        host.send_json({"type": "host_action", "payload": {"action": "validate_bt", "title": True, "artist": True}})

        # player_list emitted before reveal (scores updated)
        _read_until(host, "player_list")

        # reveal broadcast to all — now player/tv payload contains title+artist
        player_reveal = _read_until(player, "reveal")
        assert player_reveal["payload"]["title"] == "Song One"
        assert player_reveal["payload"]["artist"] == "Artist A"
        tv_reveal = _read_until(tv, "reveal")
        assert tv_reveal["payload"]["title"] == "Song One"

        # player_list carries updated score
        plist = _read_until(
            host, "player_list", where=lambda p: any(x["id"] == pid and x["score"] > 0 for x in p["players"])
        )
        alice = next(x for x in plist["payload"]["players"] if x["id"] == pid)
        assert alice["score"] == 2  # 1 title + 1 artist

        # --- next: REVEAL → SCOREBOARD ---
        host.send_json({"type": "host_action", "payload": {"action": "next"}})
        board = _read_until(tv, "scoreboard")
        assert board["payload"]["players"][0]["id"] == pid

        # --- next: SCOREBOARD → track 2 ---
        host.send_json({"type": "host_action", "payload": {"action": "next"}})
        host_bt2 = _read_until(host, "bt_track")
        assert host_bt2["payload"]["title"] == "Song Two"
        # Consume player/tv bt_track for track 2
        _read_until(player, "bt_track")
        _read_until(tv, "bt_track")


def test_blindtest_auto_pause_and_replay():
    """Integration test: auto-pause timer fires after cap elapses; replay_bt resets."""
    client = TestClient(app)
    created = client.post("/api/sessions").json()
    code, secret = created["code"], created["host_secret"]

    tracks = [
        {
            "spotify_track_id": "auto1",
            "uri": "spotify:track:auto1",
            "title": "Auto Pause Song",
            "artist": "Timer Artist",
            "cover_url": "",
            "duration_ms": 60000,
            "start_ms": 0,
            "points_title": 1,
            "points_artist": 1,
        },
    ]

    with (
        client.websocket_connect("/ws") as host,
        client.websocket_connect("/ws") as player,
    ):
        host.send_json({"type": "join", "payload": {"code": code, "role": "host", "host_secret": secret}})
        _read_until(host, "state_sync")

        player.send_json({"type": "join", "payload": {"code": code, "role": "player", "pseudo": "Bob"}})
        _read_until(player, "state_sync")
        # consume host player_list from Bob joining
        _read_until(host, "player_list")

        # Set tracks: 1 s cap, no countdown so music starts immediately
        host.send_json(
            {
                "type": "host_action",
                "payload": {
                    "action": "set_blindtest_tracks",
                    "tracks": tracks,
                    "max_play_s": 1,
                    "countdown": False,
                },
            }
        )
        _read_until(host, "prepared_blindtest")
        # consume player_list for mode switch
        _read_until(host, "player_list")

        # start — timer is armed with ~1 s delay
        host.send_json({"type": "host_action", "payload": {"action": "start_blindtest"}})

        # Host gets bt_track with audio:start
        host_bt = _read_until(host, "bt_track")
        assert host_bt["payload"]["audio"] == "start"

        # Nobody buzzes — auto-pause should arrive from the timer (~1 s later).
        # _read_until has a limit of 12 messages; the timer fires after ~1 s and
        # the TestClient event loop services it while we block on receive_json.
        auto_pause = _read_until(host, "bt_audio", limit=5)
        assert auto_pause["payload"]["audio"] == "pause"

        # replay_bt → host gets a fresh bt_track with audio:start
        host.send_json({"type": "host_action", "payload": {"action": "replay_bt"}})
        replay_bt = _read_until(host, "bt_track")
        assert replay_bt["payload"]["audio"] == "start"
