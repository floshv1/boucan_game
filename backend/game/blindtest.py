"""Pure game logic for Phase 3 (Blindtest mode, cahier §16).

Like ``game/engine.py`` and ``game/qcm.py`` this module never touches the
network: each function mutates a :class:`Session` and returns a list of
:class:`engine.Outbound` messages.

IMPORTANT — cahier §16: ``title`` / ``artist`` / ``cover_url`` / Spotify
``uri`` must NEVER appear in a payload whose target is ``"players"`` or
``"all"`` while state is before ``REVEAL``. The ``"players"`` target also
reaches TV spectators (see ws/manager.py). These fields are host-only until
the ``reveal`` message.
"""

from __future__ import annotations

import random

from game import engine, qcm
from game.engine import Outbound, player_list_payload
from game.models import ORIGIN_TYPES, BlindtestTrack, GameMode, GameState, Session
from game.store import now_ms

# --------------------------------------------------------------------------- #
# Payload builders
# --------------------------------------------------------------------------- #


def prepared_blindtest_payload(session: Session) -> dict:
    """Full prepared list with track metadata + config — host only."""
    return {
        "index": session.bt_index,
        "max_play_s": session.bt_max_play_ms // 1000,
        "random_start": session.bt_random_start,
        "countdown": session.bt_countdown_ms > 0,
        "points_title": session.bt_points_title,
        "points_artist": session.bt_points_artist,
        "points_origin": session.bt_points_origin,
        "tracks": [
            {
                "spotify_track_id": t.spotify_track_id,
                "uri": t.uri,
                "title": t.title,
                "artist": t.artist,
                "cover_url": t.cover_url,
                "duration_ms": t.duration_ms,
                "start_ms": t.start_ms,
                "points_title": t.points_title,
                "points_artist": t.points_artist,
                "bonus": t.bonus,
                "origin": t.origin,
                "origin_type": t.origin_type,
                "points_origin": t.points_origin,
            }
            for t in session.blindtest_tracks
        ],
    }


def _parse_track(item: dict) -> BlindtestTrack:
    """Parse a raw dict into a :class:`BlindtestTrack`, tolerating missing fields."""
    track_id = str(item.get("spotify_track_id") or "")
    uri = item.get("uri") or f"spotify:track:{track_id}"
    title = str(item.get("title") or "")
    artist = str(item.get("artist") or "")
    cover_url = str(item.get("cover_url") or "")
    try:
        duration_ms = max(0, int(item.get("duration_ms") or 0))
    except (TypeError, ValueError):
        duration_ms = 0
    try:
        start_ms = max(0, int(item.get("start_ms") or 0))
    except (TypeError, ValueError):
        start_ms = 0
    try:
        points_title = max(0, int(item.get("points_title") or 1))
    except (TypeError, ValueError):
        points_title = 1
    try:
        points_artist = max(0, int(item.get("points_artist") or 1))
    except (TypeError, ValueError):
        points_artist = 1
    try:
        points_origin = max(0, int(item.get("points_origin") or 1))
    except (TypeError, ValueError):
        points_origin = 1
    origin = str(item.get("origin") or "")
    origin_type = str(item.get("origin_type") or "")
    if origin_type not in ORIGIN_TYPES:
        origin_type = ""
    return BlindtestTrack(
        spotify_track_id=track_id,
        uri=uri,
        title=title,
        artist=artist,
        cover_url=cover_url,
        duration_ms=duration_ms,
        start_ms=start_ms,
        points_title=points_title,
        points_artist=points_artist,
        bonus=bool(item.get("bonus")),
        origin=origin,
        origin_type=origin_type,
        points_origin=points_origin,
    )


def _played_now(session: Session, now: int) -> int:
    """Snippet time consumed so far = accumulated + the running segment, clamped to the cap."""
    elapsed = session.bt_played_ms
    if session.bt_playing:
        elapsed += max(0, now - session.bt_play_started_at)
    if session.bt_max_play_ms > 0:
        elapsed = min(elapsed, session.bt_max_play_ms)
    return max(0, elapsed)


def _timing_block(session: Session, now: int) -> dict:
    """Pause-aware, clock-skew-safe timing, broadcast to every role (non-secret).

    Clients estimate ``serverNow`` from ``server_now`` + their own clock and compute
    elapsed = ``played_ms`` + (now - ``seg_started_at``) while ``playing``; frozen
    otherwise. ``audio_seq`` lets the host re-fire an identical directive (e.g. two
    replays in a row) that would otherwise be de-duplicated.
    """
    cur = session.blindtest_tracks[session.bt_index] if 0 <= session.bt_index < len(session.blindtest_tracks) else None
    return {
        "server_now": now,
        # ``starts_at``/``ends_at`` kept for backward compat; ``seg_started_at`` is the alias.
        "starts_at": session.bt_play_started_at,
        "seg_started_at": session.bt_play_started_at,
        "ends_at": session.bt_play_ends_at,
        "max_play_ms": session.bt_max_play_ms,
        "played_ms": session.bt_played_ms,
        "playing": session.bt_playing,
        "audio_seq": session.bt_audio_seq,
        "reveal_ends_at": session.bt_reveal_ends_at,  # non-secret: post-snippet auto-reveal countdown
        "bonus": bool(cur.bonus) if cur else False,  # non-secret: lets all clients show ×2
        "has_origin": bool(cur.origin) if cur else False,  # non-secret: an œuvre is guessable (name stays host-only)
    }


def _track_payload(session: Session, now: int, *, include_track: bool) -> dict:
    """Base payload with timing fields (non-secret, go to all); if ``include_track``
    add ``uri``, ``start_ms``, ``title``, ``artist``, ``cover_url`` (HOST ONLY)."""
    payload: dict = {
        "index": session.bt_index,
        "total": len(session.blindtest_tracks),
        **_timing_block(session, now),
    }
    if include_track and 0 <= session.bt_index < len(session.blindtest_tracks):
        t = session.blindtest_tracks[session.bt_index]
        payload["uri"] = t.uri
        payload["start_ms"] = session.bt_current_start_ms
        payload["title"] = t.title
        payload["artist"] = t.artist
        payload["cover_url"] = t.cover_url
        payload["origin"] = t.origin
        payload["origin_type"] = t.origin_type
    return payload


def _audio(session: Session, directive: str, now: int) -> Outbound:
    """Host-only audio directive (``start`` | ``resume`` | ``pause``) carrying the
    full timing block so the host's progress bar stays in sync from this message
    alone. Callers bump ``bt_audio_seq`` before calling."""
    return Outbound("host", "bt_audio", {"audio": directive, **_timing_block(session, now)})


# --------------------------------------------------------------------------- #
# Host setup actions
# --------------------------------------------------------------------------- #


def set_blindtest_tracks(
    session: Session,
    items: list[dict],
    *,
    max_play_s: int = 30,
    random_start: bool = False,
    countdown: bool = True,
    points_title: int = 1,
    points_artist: int = 1,
    points_origin: int = 1,
    buzz_answer_s: int | None = None,
    reveal_grace_s: int | None = None,
) -> list[Outbound]:
    """Replace the blindtest track list (LOBBY only) and switch to BLINDTEST mode."""
    if session.state is not GameState.LOBBY:
        return []
    session.mode = GameMode.BLINDTEST
    session.blindtest_tracks = [_parse_track(it) for it in items]
    session.bt_index = -1
    session.bt_max_play_ms = max(0, int(max_play_s)) * 1000
    if buzz_answer_s is not None:
        session.buzz_answer_ms = max(0, int(buzz_answer_s)) * 1000
    if reveal_grace_s is not None:
        session.bt_reveal_grace_ms = max(0, int(reveal_grace_s)) * 1000
    session.bt_random_start = bool(random_start)
    session.bt_countdown_ms = 3000 if countdown else 0
    session.bt_points_title = max(0, int(points_title))
    session.bt_points_artist = max(0, int(points_artist))
    session.bt_points_origin = max(0, int(points_origin))
    return [
        Outbound("host", "prepared_blindtest", prepared_blindtest_payload(session)),
        Outbound("all", "player_list", player_list_payload(session)),
    ]


# --------------------------------------------------------------------------- #
# Track navigation — shared between load_track and cont
# --------------------------------------------------------------------------- #


def _bt_track_outbounds(session: Session, now: int, audio: str) -> list[Outbound]:
    """Emit the two ``bt_track`` messages (host with track info + audio directive,
    players without), plus a ``buzz_locked`` so every client resets its buzz
    queue/floor/state to match the freshly-reset arbitration (load_track and
    cont both clear ``buzz_queue``/``floor_index`` but emit no round_state).
    Used by :func:`load_track`, :func:`cont` and :func:`replay`.

    ``audio`` is ``"start"`` (play the snippet from ``start_ms``, honouring any
    countdown) or ``"resume"`` (continue from the current position, e.g. after a buzz)."""
    return [
        Outbound("all", "buzz_locked", engine.buzz_payload(session)),
        Outbound("host", "bt_track", {**_track_payload(session, now, include_track=True), "audio": audio}),
        Outbound("players", "bt_track", _track_payload(session, now, include_track=False)),
    ]


def load_track(session: Session, index: int, now: int) -> list[Outbound]:
    """Open the track at ``index``: BUZZER_OPEN, reset buzz + bt fields."""
    if not (0 <= index < len(session.blindtest_tracks)):
        return []
    session.bt_index = index
    session.state = GameState.BUZZER_OPEN
    # Reset buzz arbitration fields
    session.buzz_queue = []
    session.buzzed_ids = set()
    session.excluded_ids = set()
    session.floor_index = 0
    session.answer_ends_at = 0
    session.revealed = False
    # Reset per-track blindtest state
    session.bt_title_by = None
    session.bt_artist_by = None
    session.bt_origin_by = None
    # Compute start offset and play timing
    track = session.blindtest_tracks[index]
    if session.bt_random_start and track.duration_ms > 0:
        session.bt_current_start_ms = random.randint(0, max(0, track.duration_ms - session.bt_max_play_ms))
    else:
        session.bt_current_start_ms = track.start_ms
    session.bt_played_ms = 0
    session.bt_playing = True
    session.bt_play_started_at = now + session.bt_countdown_ms
    session.bt_play_ends_at = session.bt_play_started_at + session.bt_max_play_ms if session.bt_max_play_ms > 0 else 0
    session.bt_reveal_ends_at = 0
    session.bt_audio_seq += 1
    return _bt_track_outbounds(session, now, "start")


def start_blindtest(session: Session, now: int) -> list[Outbound]:
    """Begin the blindtest at the first track (LOBBY only, tracks non-empty)."""
    if session.state is not GameState.LOBBY or not session.blindtest_tracks:
        return []
    for p in session.players.values():
        p.streak = 0
        p.last_rank = 0
    engine.record_game_start(session)
    return load_track(session, 0, now)


# --------------------------------------------------------------------------- #
# Buzz arbitration
# --------------------------------------------------------------------------- #


def on_buzz(session: Session, player_id: str, now: int) -> list[Outbound]:
    """Delegate to engine.buzz; keep only ``buzz_locked``, append ``bt_audio pause``
    when the floor is newly acquired."""
    if now < session.bt_play_started_at:
        return []
    raw = engine.buzz(session, player_id, now)
    if not raw:
        return []
    outs = [o for o in raw if o.type == "buzz_locked"]
    if session.state is GameState.BUZZED:
        # Someone holds the floor → the post-snippet auto-reveal grace is suspended.
        session.bt_reveal_ends_at = 0
        if session.bt_playing:
            # First buzz to land while playing freezes the running snippet clock.
            session.bt_played_ms = _played_now(session, now)
            session.bt_playing = False
            session.bt_play_ends_at = 0
        # Re-emit the pause directive on *every* buzz while a floor is held — not only
        # the floor-acquiring one. This self-heals the reported bug where a second
        # buzzer (or a host that missed the first pause) kept the music playing:
        # pausing an already-paused player is a no-op, and bumping bt_audio_seq forces
        # the host audio effect to re-fire.
        session.bt_audio_seq += 1
        outs.append(_audio(session, "pause", now))
        # players/TV freeze their progress bar (no track secrets, §16-safe)
        outs.append(Outbound("players", "bt_track", _track_payload(session, now, include_track=False)))
    return outs


# --------------------------------------------------------------------------- #
# Host judge actions
# --------------------------------------------------------------------------- #


def _bt_award(session: Session, track: BlindtestTrack) -> tuple[int, int, int]:
    """Title/artist/origin points for a track: global session values, doubled on a bonus song."""
    mult = 2 if track.bonus else 1
    return (
        session.bt_points_title * mult,
        session.bt_points_artist * mult,
        session.bt_points_origin * mult,
    )


def _all_targets_found(session: Session, track: BlindtestTrack) -> bool:
    """True once every applicable target for this track is credited: title + artist,
    plus origin only when the track defines one."""
    return (
        session.bt_title_by is not None
        and session.bt_artist_by is not None
        and (session.bt_origin_by is not None or not track.origin)
    )


def validate(
    session: Session, *, title: bool, artist: bool, origin: bool = False, now: int | None = None
) -> list[Outbound]:
    """Award title/artist/origin points to the floor player; auto-reveal when all
    applicable targets are found (origin counts only when the track defines one)."""
    if session.state is not GameState.BUZZED or session.floor_player_id is None:
        return []
    if now is None:
        now = now_ms()
    if not title and not artist and not origin:  # no-op validate: emit nothing
        return []
    pid = session.floor_player_id
    track = session.blindtest_tracks[session.bt_index]
    player = session.players[pid]
    pts_title, pts_artist, pts_origin = _bt_award(session, track)
    session.answer_ends_at = 0  # judged: stop the post-buzz answer countdown

    if title and session.bt_title_by is None:
        player.score += pts_title
        session.bt_title_by = pid
    if artist and session.bt_artist_by is None:
        player.score += pts_artist
        session.bt_artist_by = pid
    if origin and track.origin and session.bt_origin_by is None:
        player.score += pts_origin
        session.bt_origin_by = pid

    outs: list[Outbound] = [Outbound("all", "player_list", player_list_payload(session))]

    if _all_targets_found(session, track):
        # Every applicable target found → auto-reveal
        outs.extend(reveal(session, now))
    else:
        outs.append(
            Outbound(
                "host",
                "bt_partial",
                {
                    "title_by": session.bt_title_by,
                    "artist_by": session.bt_artist_by,
                    "origin_by": session.bt_origin_by,
                },
            )
        )
    return outs


def cont(session: Session, now: int) -> list[Outbound]:
    """'Continuer': reopen the buzzer for the remaining point (BUZZED only).

    The player(s) who already scored (title and/or artist) are barred from
    re-buzzing for the remaining point — only the others may go for it."""
    if session.state is not GameState.BUZZED:
        return []
    session.state = GameState.BUZZER_OPEN
    session.buzz_queue = []
    session.buzzed_ids = set()
    session.excluded_ids = {
        pid for pid in (session.bt_title_by, session.bt_artist_by, session.bt_origin_by) if pid
    }
    session.floor_index = 0
    session.answer_ends_at = 0
    session.bt_reveal_ends_at = 0
    session.revealed = False  # engine.buzz rejects buzzes while revealed is True
    # Resume the snippet clock from where the buzz froze it (keep bt_played_ms, no
    # countdown). The remaining budget is the cap minus what's already been played.
    session.bt_playing = True
    session.bt_play_started_at = now
    remaining = session.bt_max_play_ms - session.bt_played_ms
    session.bt_play_ends_at = now + max(0, remaining) if session.bt_max_play_ms > 0 else 0
    session.bt_audio_seq += 1
    return _bt_track_outbounds(session, now, "resume")


def invalidate(session: Session, now: int | None = None) -> list[Outbound]:
    """Wrong oral answer: delegate to engine.invalidate (which bars the fautif and
    clears the queue), then resume the snippet from where the buzz froze it."""
    raw = engine.invalidate(session)
    if not raw:
        return []
    if now is None:
        now = now_ms()
    outs = [o for o in raw if o.type == "buzz_locked"]
    session.bt_audio_seq += 1
    # engine.invalidate always reopens the buzzer (BUZZER_OPEN) now.
    remaining = session.bt_max_play_ms - session.bt_played_ms
    if session.bt_max_play_ms > 0 and remaining <= 0:
        # The snippet was already exhausted (wrong answer during the post-music grace):
        # stay paused and re-arm the auto-reveal grace instead of a 0-length resume.
        session.bt_playing = False
        session.bt_play_ends_at = 0
        session.bt_reveal_ends_at = now + session.bt_reveal_grace_ms if session.bt_reveal_grace_ms > 0 else 0
        outs.append(_audio(session, "pause", now))
    else:
        # Resume the snippet from where the buzz froze it.
        session.bt_playing = True
        session.bt_play_started_at = now
        session.bt_play_ends_at = now + max(0, remaining) if session.bt_max_play_ms > 0 else 0
        outs.append(_audio(session, "resume", now))
    outs.append(Outbound("players", "bt_track", _track_payload(session, now, include_track=False)))
    return outs


def reveal(session: Session, now: int | None = None) -> list[Outbound]:
    """Manually reveal the track (or called internally by validate on full answer).
    Only valid in BUZZER_OPEN or BUZZED."""
    if session.state not in (GameState.BUZZER_OPEN, GameState.BUZZED):
        return []
    if now is None:
        now = now_ms()
    track = session.blindtest_tracks[session.bt_index]
    pts_title, pts_artist, pts_origin = _bt_award(session, track)

    # Build score deltas from who already won points this track
    deltas: dict[str, int] = {}
    if session.bt_title_by is not None:
        deltas[session.bt_title_by] = deltas.get(session.bt_title_by, 0) + pts_title
    if session.bt_artist_by is not None:
        deltas[session.bt_artist_by] = deltas.get(session.bt_artist_by, 0) + pts_artist
    if session.bt_origin_by is not None:
        deltas[session.bt_origin_by] = deltas.get(session.bt_origin_by, 0) + pts_origin

    session.state = GameState.REVEAL
    session.bt_playing = False
    session.bt_play_ends_at = 0
    session.bt_reveal_ends_at = 0
    session.bt_audio_seq += 1
    return [
        Outbound(
            "all",
            "reveal",
            {
                "title": track.title,
                "artist": track.artist,
                "cover_url": track.cover_url,
                "origin": track.origin,
                "origin_type": track.origin_type,
                "deltas": deltas,
            },
        ),
        Outbound("all", "player_list", player_list_payload(session)),
        _audio(session, "pause", now),
    ]


# --------------------------------------------------------------------------- #
# Scoreboard + progression (reuse QCM helpers)
# --------------------------------------------------------------------------- #


def to_scoreboard(session: Session, now: int | None = None) -> list[Outbound]:
    """Delegate to qcm.to_scoreboard (mode-agnostic, score-based ▲/▼)."""
    if now is None:
        now = now_ms()
    session.bt_playing = False
    session.bt_play_ends_at = 0
    session.bt_audio_seq += 1
    return [*qcm.to_scoreboard(session), _audio(session, "pause", now)]


def next_(session: Session, now: int) -> list[Outbound]:
    """Advance to the next track, or end the game if the list is exhausted."""
    if session.state is not GameState.SCOREBOARD:
        return []
    if session.bt_index + 1 < len(session.blindtest_tracks):
        return load_track(session, session.bt_index + 1, now)
    session.state = GameState.GAME_END
    engine.record_game_end(session, "blindtest")
    return [Outbound("all", "game_end", qcm.game_end_payload(session))]


def on_play_timeout(session: Session, now: int | None = None) -> list[Outbound]:
    """Max play time elapsed with nobody holding the floor → pause the snippet but keep
    the round open for a short grace so players can still buzz after the music; arm an
    auto-reveal at the end of that grace (cahier: 'si le temps est dépassé, révéler')."""
    if session.state is GameState.BUZZER_OPEN and not session.revealed and session.floor_player_id is None:
        if now is None:
            now = now_ms()
        session.bt_played_ms = _played_now(session, now)
        session.bt_playing = False
        session.bt_play_ends_at = 0
        session.bt_reveal_ends_at = now + session.bt_reveal_grace_ms if session.bt_reveal_grace_ms > 0 else 0
        session.bt_audio_seq += 1
        return [
            _audio(session, "pause", now),
            Outbound("players", "bt_track", _track_payload(session, now, include_track=False)),
        ]
    return []


def pause_bt(session: Session, now: int) -> list[Outbound]:
    """Host 'Pause' toggle: freeze the snippet clock (BUZZER_OPEN + playing only)."""
    if session.state is not GameState.BUZZER_OPEN or not session.bt_playing:
        return []
    session.bt_played_ms = _played_now(session, now)
    session.bt_playing = False
    session.bt_play_ends_at = 0
    session.bt_audio_seq += 1
    return [
        _audio(session, "pause", now),
        Outbound("players", "bt_track", _track_payload(session, now, include_track=False)),
    ]


def resume_bt(session: Session, now: int) -> list[Outbound]:
    """Host 'Lecture' toggle when paused: resume the snippet from where it froze."""
    if session.state is not GameState.BUZZER_OPEN or session.bt_playing:
        return []
    session.bt_playing = True
    session.bt_play_started_at = now
    remaining = session.bt_max_play_ms - session.bt_played_ms
    session.bt_play_ends_at = now + max(0, remaining) if session.bt_max_play_ms > 0 else 0
    session.bt_reveal_ends_at = 0  # music playing again → cancel any pending auto-reveal
    session.bt_audio_seq += 1
    return [
        _audio(session, "resume", now),
        Outbound("players", "bt_track", _track_payload(session, now, include_track=False)),
    ]


def replay(session: Session, now: int) -> list[Outbound]:
    """Replay the current track snippet from its start, resetting the play timer."""
    if session.state is not GameState.BUZZER_OPEN:
        return []
    session.bt_played_ms = 0
    session.bt_playing = True
    session.bt_play_started_at = now
    session.bt_play_ends_at = now + session.bt_max_play_ms if session.bt_max_play_ms > 0 else 0
    session.bt_reveal_ends_at = 0  # fresh snippet → cancel any pending auto-reveal
    session.bt_audio_seq += 1
    return _bt_track_outbounds(session, now, "start")


def mark_started(session: Session, now: int) -> list[Outbound]:
    """The host confirms audio actually began playing → re-anchor the play window
    to ``now``. The auto-pause is otherwise anchored to the message dispatch time,
    so SDK-readiness / ``play()`` latency / the countdown would cut the snippet
    short ("la musique s'arrête avant la fin"). No audio directive and no
    ``bt_audio_seq`` bump → the host's audio effect won't re-fire."""
    if session.state is not GameState.BUZZER_OPEN or not session.bt_playing:
        return []
    session.bt_play_started_at = now
    remaining = session.bt_max_play_ms - session.bt_played_ms
    session.bt_play_ends_at = now + max(0, remaining) if session.bt_max_play_ms > 0 else 0
    return [
        Outbound("host", "bt_track", _track_payload(session, now, include_track=True)),
        Outbound("players", "bt_track", _track_payload(session, now, include_track=False)),
    ]


def replay_game(session: Session, now: int) -> list[Outbound]:
    """Restart the whole blindtest from the first track with scores reset (GAME_END
    only), so the host can replay the same playlist without recreating the game."""
    if session.state is not GameState.GAME_END:
        return []
    for p in session.players.values():
        p.score = 0
        p.streak = 0
        p.last_rank = 0
    session.state = GameState.LOBBY  # let start_blindtest's guard pass
    session.bt_index = -1
    return [
        Outbound("all", "player_list", player_list_payload(session)),
        *start_blindtest(session, now),
    ]


# --------------------------------------------------------------------------- #
# Reconnection state sync
# --------------------------------------------------------------------------- #


def state_sync_payload(session: Session, *, role: str, player_id: str | None = None) -> dict:
    """Blindtest section for the global state_sync (reconnection, cahier §13).

    §16 applies: title/artist/uri must NOT appear for non-host roles before REVEAL.
    """
    data: dict = {
        "mode": session.mode.value,
        "state": session.state.value,
        "index": session.bt_index,
        "total": len(session.blindtest_tracks),
    }
    if session.state in (GameState.BUZZER_OPEN, GameState.BUZZED):
        # Merge track payload fields directly into data (incl. pause-aware timing)
        track_fields = _track_payload(session, now_ms(), include_track=(role == "host"))
        data.update(track_fields)
        if role == "host":
            data["audio"] = "resume" if session.bt_playing else "pause"
    elif session.state is GameState.REVEAL:
        if 0 <= session.bt_index < len(session.blindtest_tracks):
            t = session.blindtest_tracks[session.bt_index]
            data["reveal"] = {
                "title": t.title,
                "artist": t.artist,
                "cover_url": t.cover_url,
                "origin": t.origin,
                "origin_type": t.origin_type,
            }
    elif session.state is GameState.GAME_END:
        data["game_end"] = qcm.game_end_payload(session)
    return data
