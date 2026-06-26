"""In-memory data model for a live quiz session (Phase 1: buzzer mode).

Everything here is ephemeral — it lives in RAM and is reset when the server
restarts (cahier §15). No database is involved in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GameState(StrEnum):
    """Lifecycle states (cahier §12). Buzzer + QCM share this enum."""

    LOBBY = "LOBBY"
    # Buzzer
    BUZZER_OPEN = "BUZZER_OPEN"
    BUZZED = "BUZZED"
    # QCM
    QUESTION_ACTIVE = "QUESTION_ACTIVE"
    REVEAL = "REVEAL"
    SCOREBOARD = "SCOREBOARD"
    GAME_END = "GAME_END"


class GameMode(StrEnum):
    BUZZER = "buzzer"
    QCM = "qcm"
    BLINDTEST = "blindtest"


@dataclass
class Player:
    id: str
    pseudo: str
    reconnect_token: str
    score: int = 0
    connected: bool = True
    streak: int = 0  # consecutive correct QCM answers
    last_rank: int = 0  # rank at the previous scoreboard, for ▲/▼ deltas


@dataclass
class BuzzEntry:
    """One buzz, in arrival order, as arbitrated by the server (cahier §14)."""

    player_id: str
    ts: int  # server receive timestamp (ms)
    order: int  # 1-based arrival rank
    delta_ms: int  # gap vs the first buzz of the round


@dataclass
class PreparedRound:
    """A buzzer round prepared by the host *before* the game starts, so nothing
    is typed live on a shared screen (itération 2). ``question_text`` may be
    ``None`` for a pure-buzzer round (e.g. blindtest)."""

    question_text: str | None = None
    answer: str | None = None
    points: int = 1
    bonus: bool = False  # ×2 points when set
    image: str | None = None  # optional prompt image URL (/media/...), shown during the round


@dataclass
class QcmRound:
    """A QCM question prepared by the host before the game (cahier §4.3)."""

    question: str
    choices: list[str]  # exactly 4, in original (editor) order
    correct: int  # index 0..3 in original order
    time_limit: int = 20  # seconds
    points: int = 1000  # base points
    bonus: bool = False  # ×2 base points when set
    image: str | None = None  # optional prompt image URL (/media/...), shown during the question


@dataclass
class BlindtestTrack:
    """A single track in a blindtest prepared list (Phase 3, cahier §16)."""

    spotify_track_id: str
    uri: str  # "spotify:track:<id>"
    title: str
    artist: str
    cover_url: str = ""
    duration_ms: int = 0
    start_ms: int = 0
    points_title: int = 1  # legacy per-track points (kept for pack storage); awards use session globals
    points_artist: int = 1
    bonus: bool = False  # ×2 points (title + artist) when set


@dataclass
class QcmAnswer:
    """A player's answer to the current question. ``choice`` is an index in the
    *presented* order; correctness/points are filled at REVEAL."""

    choice: int
    ts: int  # server receive timestamp (ms)
    correct: bool = False
    awarded: int = 0


@dataclass
class Session:
    code: str
    host_secret: str
    created_at: int
    last_seen: int = 0  # epoch ms of the last activity; idle sessions are evicted (store)
    state: GameState = GameState.LOBBY
    players: dict[str, Player] = field(default_factory=dict)

    # Prepared round list (itération 2). round_index == -1 → not started / lobby.
    rounds: list[PreparedRound] = field(default_factory=list)
    round_index: int = -1

    # Current round (reset on open_buzzer / next)
    question_text: str | None = None
    answer: str | None = None
    points: int = 1
    bonus: bool = False  # current buzzer round is a ×2 bonus
    image: str | None = None  # optional prompt image URL for the current buzzer round
    revealed: bool = False
    buzz_open_at: int = 0  # epoch ms the buzzer actually opens (after the reading window)
    buzz_limit_ms: int = 20000  # per-round buzzer countdown; auto-reveal when it elapses (0 = no limit)
    buzz_ends_at: int = 0  # epoch ms the open buzzer auto-reveals (0 = no limit / not open)
    buzz_queue: list[BuzzEntry] = field(default_factory=list)
    buzzed_ids: set[str] = field(default_factory=set)  # idempotence guard
    floor_index: int = 0  # index into buzz_queue of the player holding the floor

    # Blindtest mode (Phase 3). Track list and per-track state.
    blindtest_tracks: list[BlindtestTrack] = field(default_factory=list)
    bt_index: int = -1
    bt_title_by: str | None = None  # player_id who got the title on the current track
    bt_artist_by: str | None = None  # player_id who got the artist on the current track
    bt_max_play_ms: int = 30000  # per-game cap on snippet length (0 = no cap)
    bt_points_title: int = 1  # global points for guessing the title (×2 on bonus songs)
    bt_points_artist: int = 1  # global points for guessing the artist (×2 on bonus songs)
    bt_random_start: bool = False  # start each track at a random offset
    bt_countdown_ms: int = 3000  # 3-2-1 pre-roll before a track (0 = none)
    bt_play_started_at: int = 0  # epoch ms the current play segment's clock started (incl. countdown)
    bt_play_ends_at: int = 0  # epoch ms the server auto-pauses the current segment (0 = no cap / paused)
    bt_current_start_ms: int = 0  # the start offset chosen for the current track (host payload)
    # Pause-aware accounting: the progress bar is driven by accumulated *played* time,
    # not wall-clock, so it freezes on pause/buzz and survives clock skew (clients
    # correct against ``server_now``). ``bt_play_started_at`` doubles as the current
    # segment's start; ``bt_played_ms`` is the time consumed in earlier segments.
    bt_played_ms: int = 0  # snippet time already consumed across previous (paused) segments
    bt_playing: bool = False  # whether the snippet clock is currently running
    bt_audio_seq: int = 0  # bumped on every audio-affecting transition (defeats client URI de-dup)

    # QCM mode (Phase 2). Live state for the current question.
    mode: GameMode = GameMode.BUZZER
    qcm_shuffle_questions: bool = False
    qcm_shuffle_choices: bool = False
    qcm_rounds: list[QcmRound] = field(default_factory=list)
    qcm_index: int = -1
    question_started_at: int = 0
    question_ends_at: int = 0
    answers: dict[str, QcmAnswer] = field(default_factory=dict)
    presented_order: list[int] = field(default_factory=lambda: [0, 1, 2, 3])

    @property
    def floor_player_id(self) -> str | None:
        """The player who currently has the right to answer, if any."""
        if self.state is GameState.BUZZED and 0 <= self.floor_index < len(self.buzz_queue):
            return self.buzz_queue[self.floor_index].player_id
        return None
