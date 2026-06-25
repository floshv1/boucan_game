# Blindtest v2 — Design

Date: 2026-06-24 · Builds on Phase 3 (Blindtest). Cahier §16, §22.

## Context

The blindtest mode works (live-verified) but real use surfaced UX gaps. This sub-project polishes
the blindtest experience only. The bigger **multi-mode game builder** (§21), broad cross-mode
**UX polish**, and an **OpenTDB trivia importer** are explicitly parked for later cycles.

The headline new capability is a **server-driven synced timer** for blindtest (it has none today),
mirroring the QCM `ends_at` pattern so the TV and phones render the countdown, the play progress,
and the max-time bar in sync.

Decisions locked in brainstorming:
- Max play time elapses with nobody buzzed → **auto-pause, round stays open, host decides** (Révéler / Suivant).
- Timer + 3-2-1 countdown + progress bar are **synced on all screens** (host, players, TV).

## Features

- **A. Stop audio on reveal + scoreboard.** Today `reveal()` does not pause; music bleeds into the
  scoreboard. Reveal, skip, and scoreboard must pause the host audio.
- **B. Random start.** Per-game toggle. When on, each track starts at a random offset computed from
  its `duration_ms`; when off, the per-track `start_ms` is used.
- **C. Max play time.** Per-game setting in seconds (default 30). At the cap the server auto-pauses
  the host audio; the round stays `BUZZER_OPEN` (host reveals/advances).
- **D. Volume control.** Live host slider → Spotify SDK volume (client-only; persists across tracks).
- **E. 3-2-1 countdown before each track.** Synced; the music starts and the buzzer opens only when
  the countdown ends.
- **F. Replay button.** Host restarts the current snippet from its start and resets the timer/progress
  (no new countdown, same `start_ms`).
- **G. Progress bar.** Synced playback progress (start → max-time) on host + phones + TV. The
  progress bar and the auto-pause are active only when a cap is set (`max_play_ms > 0`); with no cap
  the music plays until the host acts and no progress bar is shown.

## Architecture

### Session state (new fields on `Session`, `game/models.py`)
- `bt_max_play_ms: int = 30000` — per-game cap (0 = no cap / play track out; default 30 s).
- `bt_random_start: bool = False`
- `bt_countdown_ms: int = 3000` — pre-roll before a track (0 = no countdown).
- `bt_play_started_at: int = 0` — epoch ms when the music actually starts (after the countdown).
- `bt_play_ends_at: int = 0` — epoch ms the server auto-pauses (= started_at + max_play_ms; 0 = no cap).

Volume is **not** server state (client-only).

### Config intake
`set_blindtest_tracks` (or `start_blindtest`) payload gains optional `max_play_s` (int),
`random_start` (bool), `countdown` (bool). Stored as the session fields above
(`bt_max_play_ms = max_play_s*1000`, etc.). The host config block gets a small settings row.

### Track start handshake (countdown + timer) — `game/blindtest.py`
`load_track(session, index, now)` (now takes `now`):
1. Compute `start_ms`: if `bt_random_start` and `duration_ms > 0` →
   `randint(0, max(0, duration_ms - bt_max_play_ms))`; else the track's `start_ms`.
2. `bt_play_started_at = now + bt_countdown_ms` (music starts after the countdown).
3. `bt_play_ends_at = bt_play_started_at + bt_max_play_ms` (or 0 if no cap).
4. State `BUZZER_OPEN`, reset buzz + per-track fields (as today), emit `buzz_locked` + `bt_track`.

`bt_track` payload gains `starts_at` (=`bt_play_started_at`), `ends_at` (=`bt_play_ends_at`),
`max_play_ms`. Host variant keeps `uri`/`start_ms`/title/artist/cover (§16 unchanged); players/tv get
`index`, `total`, `starts_at`, `ends_at`, `max_play_ms` (timing only — no secrets).

**Buzz gate:** `on_buzz` rejects buzzes while `now < bt_play_started_at` (during the countdown).

**Host SDK behavior** (`BlindtestStage`): on `bt_track`, if `starts_at` is in the future, show the
3-2-1 countdown and defer `spotify.play(uri, start_ms)` until `starts_at`; players/tv show the same
countdown from `starts_at`. After `starts_at`, render the progress bar over `[starts_at, ends_at]`.

### Server timer (`main.py`)
Add `_sync_blindtest_timer(session)` mirroring `_sync_qcm_timer`: schedule an async task that fires at
`bt_play_ends_at`. On fire, if still `BUZZER_OPEN`, not revealed, no floor → dispatch
`blindtest.on_play_timeout(session)` which emits `bt_audio: pause` to host (round stays open). Cancel
the timer on buzz, reveal, skip, next, replay, and game end. No timer when `bt_max_play_ms == 0`.

### Reveal / scoreboard / replay
- `reveal()` and `to_scoreboard()` append `_audio("pause")` (feature A) and the controller cancels the
  timer.
- `replay_bt` host action: `bt_play_started_at = now`, `bt_play_ends_at = now + bt_max_play_ms`,
  re-emit `bt_track` (audio `play`, same `start_ms`, no countdown), reschedule the timer.
- `cont()` (partial → continue) already reopens the buzzer; give it the same play timing as a fresh
  play (new started_at/ends_at, optional countdown skipped).

### Volume (D) — frontend only
`useSpotifyPlayer` exposes `volume`, `setVolume(v: number)` (calls `player.setVolume`, default 0.8,
persisted in a ref so it survives track changes). `BlindtestStage` adds a slider.

### §16
Timing fields (`starts_at`/`ends_at`/`max_play_ms`/progress/countdown) carry no answers; random
`start_ms` is host-only as before. No change to the reveal-gating of title/artist/cover.

## Frontend
- **Host config:** settings row (max play time s, random-start toggle, countdown toggle).
- **`BlindtestStage` (host):** countdown overlay + deferred play; progress bar; **Replay** button
  (`replay_bt`); **volume slider**; existing controls intact. The audio effect respects `starts_at`.
- **Player + TV:** 3-2-1 countdown before the track; a synced progress bar during play (reuse the
  `Countdown`/`ends_at` pattern). No audio (host only).
- **Reducer (`useGameSocket`):** carry `starts_at`/`ends_at`/`max_play_ms` into `blindtest` state from
  `bt_track`; clear/freeze on buzz/reveal.

## Verification
- **Backend:** unit tests for random-start bounds, countdown timing (`starts_at = now + countdown`),
  buzz rejected during countdown, auto-pause emission at timeout (round stays `BUZZER_OPEN`), audio
  pause on reveal + scoreboard, replay resets timing. WS integration test for the timer firing
  (no hang, pytest-timeout=30). ruff clean.
- **Frontend:** `npm run build` green.
- **Manual:** start a blindtest → 3-2-1 on all screens → music plays with a synced progress bar →
  let the cap elapse → host audio auto-pauses, round open → Replay restarts → volume slider works →
  validate/skip → music stops before the scoreboard. Random-start on → different entry each play.

## Out of scope (explicit)
Multi-mode game builder (§21); cross-mode UX/animation polish; OpenTDB trivia importer; per-track
(vs per-game) timing settings; continuous fine-grained playback position polling (progress is derived
from `starts_at`/`ends_at`, not live SDK position).
