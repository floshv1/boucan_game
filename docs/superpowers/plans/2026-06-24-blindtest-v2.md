# Blindtest v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-driven synced timer to blindtest plus random start, max play time, 3-2-1 countdown, replay, host volume, a progress bar, and audio-stop on reveal/scoreboard.

**Architecture:** New `Session` timing fields (`bt_play_started_at`/`bt_play_ends_at`) drive a synced countdown + progress bar on all clients (reusing the QCM `ends_at`/`Countdown` pattern). A `_sync_blindtest_timer` in `main.py` mirrors `_sync_qcm_timer` to auto-pause at the cap. The host SDK defers `play()` until `starts_at`; the backend rejects buzzes during the countdown. Volume is client-only.

**Tech Stack:** Backend FastAPI + uv + ruff + pytest. Frontend Next.js 15 / React 19 / TS strict.

## Global Constraints

- **NO git commands** — checkpoints update the ledger, not commits.
- Backend: `ruff check` + `ruff format --check` clean (line-length 120, E/F/W/I/UP); `pytest` green (asyncio_mode=auto, **pytest-timeout=30 — no hangs**). Run via `uv run`.
- Frontend: TS strict; gate = `npm run build`; no eslint errors.
- **§16 unchanged:** timing/countdown/progress fields carry NO answers; title/artist/cover/uri stay host-only until REVEAL. Random `start_ms` is host-only (already absent from player/tv payloads).
- A game is 100% one mode; do not change buzzer/QCM logic. Blindtest timer reuses the `_qcm_timers` dict (a session is one mode, so the single per-code timer slot is shared safely).
- Defaults: `bt_max_play_ms=30000` (30 s; 0 = no cap → no timer, no progress bar), `bt_countdown_ms=3000`, `bt_random_start=False`.

**Ledger:** create `docs/superpowers/plans/2026-06-24-blindtest-v2-progress.md` (mirror the Phase 4 ledger); tick tasks there at each checkpoint. No commits.

---

### Task 1: Backend — `Session` timing fields + config intake

**Files:**
- Modify: `backend/game/models.py` (`Session`: add the 5 fields)
- Modify: `backend/game/blindtest.py` (`set_blindtest_tracks` reads config from payload)
- Test: extend `backend/tests/test_blindtest.py`

**Interfaces — Produces:**
- `Session.bt_max_play_ms: int = 30000`, `Session.bt_random_start: bool = False`,
  `Session.bt_countdown_ms: int = 3000`, `Session.bt_play_started_at: int = 0`,
  `Session.bt_play_ends_at: int = 0`.
- `set_blindtest_tracks(session, items, *, max_play_s=30, random_start=False, countdown=True)` — sets
  `bt_max_play_ms = max(0, int(max_play_s))*1000`, `bt_random_start = bool(random_start)`,
  `bt_countdown_ms = 3000 if countdown else 0`.

- [ ] **Step 1: Write failing test** (in `test_blindtest.py`):

```python
def test_set_blindtest_tracks_stores_config():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=15, random_start=True, countdown=False)
    assert session.bt_max_play_ms == 15000
    assert session.bt_random_start is True
    assert session.bt_countdown_ms == 0
```

(Use the existing `_TWO_TRACKS` / `_session_with_players` helpers in that file.)

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_blindtest.py -k config -q` → FAIL.
- [ ] **Step 3: Implement** the model fields + the `set_blindtest_tracks` keyword args.
- [ ] **Step 4: Run** — targeted + full `uv run pytest -q` → PASS; ruff clean.
- [ ] **Step 5: Checkpoint** — tick Task 1 in ledger.

---

### Task 2: Backend — countdown + random start + timing payload in `load_track`/`on_buzz`

**Files:**
- Modify: `backend/game/blindtest.py` (`load_track`, `start_blindtest`, `next_`, `cont`, `on_buzz`,
  `_track_payload`/`_bt_track_outbounds`)
- Test: extend `backend/tests/test_blindtest.py`

**Interfaces — Produces:**
- `load_track(session, index, now: int)` (now-aware). Sets:
  - `start_ms`: if `bt_random_start and track.duration_ms > 0` →
    `random.randint(0, max(0, track.duration_ms - bt_max_play_ms))`, else `track.start_ms`.
    Store the chosen value on the session for the payload (e.g. local var used in the payload; the
    host needs the actual `start_ms`).
  - `bt_play_started_at = now + bt_countdown_ms`
  - `bt_play_ends_at = bt_play_started_at + bt_max_play_ms if bt_max_play_ms > 0 else 0`
- `start_blindtest(session, now)`, `next_(session, now)`, `cont(session, now)` — all now-aware; `cont`
  sets `bt_play_started_at = now` (no countdown) and `bt_play_ends_at` accordingly.
- `bt_track` payload (both host and players/tv) gains `starts_at` (=`bt_play_started_at`),
  `ends_at` (=`bt_play_ends_at`), `max_play_ms` (=`bt_max_play_ms`). Host still includes
  `uri`/`start_ms`/title/artist/cover (the random `start_ms` goes ONLY to host).
- `on_buzz(session, player_id, now)` — reject (return `[]`) when `now < session.bt_play_started_at`
  (countdown not finished); otherwise unchanged (delegates to `engine.buzz`, appends audio pause).

**Note:** the host needs the chosen random `start_ms` in its `bt_track`. Easiest: store it on a session
field `bt_current_start_ms: int = 0` (add to models in this task) so `_track_payload(include_track=True)`
emits it; players/tv never get `start_ms`.

- [ ] **Step 1: Write failing tests:**

```python
def test_countdown_sets_started_and_ends_at():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10, countdown=True)
    blindtest.start_blindtest(session, now=1000)
    assert session.bt_play_started_at == 1000 + 3000
    assert session.bt_play_ends_at == session.bt_play_started_at + 10000


def test_buzz_rejected_during_countdown():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, countdown=True)
    blindtest.start_blindtest(session, now=1000)
    # started_at == 4000; a buzz at 2000 is during the countdown → ignored
    assert blindtest.on_buzz(session, alice.id, now=2000) == []
    # a buzz after started_at locks the floor
    outs = blindtest.on_buzz(session, alice.id, now=5000)
    assert any(o.type == "buzz_locked" for o in outs)


def test_bt_track_payload_has_timing_no_secrets_for_players():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10)
    outs = blindtest.start_blindtest(session, now=0)
    players = [o for o in outs if o.type == "bt_track" and o.target == "players"][0]
    assert players.payload["max_play_ms"] == 10000
    assert "ends_at" in players.payload and "starts_at" in players.payload
    assert "title" not in players.payload and "start_ms" not in players.payload


def test_random_start_within_bounds():
    session, _ = _session_with_players("Alice")
    # _TWO_TRACKS[0] has a known duration_ms; ensure your fixture sets one (e.g. 200000)
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=10, random_start=True)
    blindtest.start_blindtest(session, now=0)
    host = ...  # bt_track host payload
    assert 0 <= host.payload["start_ms"] <= 200000 - 10000
```

(If `_TWO_TRACKS` lacks `duration_ms`, add it to the fixture in this task so the random-start bound is
testable; keep other blindtest tests green.)

- [ ] **Step 2: Run to verify they fail** — FAIL.
- [ ] **Step 3: Implement.** Update the now-aware signatures and the payload. Update all in-module
  callers. `import random` already present.
- [ ] **Step 4: Run** — full `uv run pytest -q` → PASS (fix any callers in `main.py` you touched only
  via signatures — but `main.py` wiring is Task 3; for this task keep `blindtest.py` self-consistent and
  update its own callers). ruff clean.
- [ ] **Step 5: Checkpoint** — tick Task 2.

---

### Task 3: Backend — reveal/scoreboard audio-stop, `on_play_timeout`, `replay_bt`, timer wiring in `main.py`

**Files:**
- Modify: `backend/game/blindtest.py` (`reveal`, `to_scoreboard`, new `on_play_timeout`, new `replay`)
- Modify: `backend/main.py` (`_sync_blindtest_timer`, `_auto_pause_blindtest`, route `replay_bt`,
  call the timer after blindtest host actions + buzz, now-args into blindtest actions)
- Test: extend `backend/tests/test_blindtest.py` and `backend/tests/test_ws.py`

**Interfaces — Produces:**
- `reveal(session)` and `to_scoreboard(session)` append `_audio("pause")` (feature A).
- `on_play_timeout(session) -> list[Outbound]` — if `state is BUZZER_OPEN` and not `revealed` and no
  floor → `[_audio("pause")]`; else `[]`.
- `replay(session, now) -> list[Outbound]` — `bt_play_started_at = now`,
  `bt_play_ends_at = now + bt_max_play_ms if bt_max_play_ms else 0`, re-emit the `bt_track` outbounds
  (audio `play`, same `bt_current_start_ms`, no countdown).
- `main.py`: `BLINDTEST_ONLY_ACTIONS` gains `"replay_bt"`. `_run_blindtest_host_action` passes
  `now_ms()` to `start_blindtest`/`next_`/`cont`/`replay`. After dispatching a blindtest host action
  AND after a blindtest buzz, call `await _sync_blindtest_timer(session)`.
- `_sync_blindtest_timer(session)`: `_cancel_timer(code)`; if `state is BUZZER_OPEN` and
  `bt_play_ends_at > 0` → schedule `_auto_pause_blindtest` at `(bt_play_ends_at - now_ms())/1000`.
- `_auto_pause_blindtest(session, delay)`: sleep; if `state is BUZZER_OPEN and not revealed` →
  `await manager.dispatch(session, blindtest.on_play_timeout(session))`; swallow `CancelledError`.

- [ ] **Step 1: Write failing tests:**

```python
# test_blindtest.py
def test_reveal_pauses_audio():
    session, [alice] = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS)
    blindtest.start_blindtest(session, now=0)
    blindtest.on_buzz(session, alice.id, now=5000)
    outs = blindtest.validate(session, title=True, artist=True)  # auto-reveal
    assert any(o.type == "bt_audio" and o.payload["audio"] == "pause" for o in outs)


def test_on_play_timeout_pauses_when_open():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=5)
    blindtest.start_blindtest(session, now=0)
    outs = blindtest.on_play_timeout(session)
    assert [o.payload["audio"] for o in outs if o.type == "bt_audio"] == ["pause"]


def test_replay_resets_timing_and_plays():
    session, _ = _session_with_players("Alice")
    blindtest.set_blindtest_tracks(session, _TWO_TRACKS, max_play_s=8)
    blindtest.start_blindtest(session, now=0)
    outs = blindtest.replay(session, now=20000)
    assert session.bt_play_started_at == 20000
    assert session.bt_play_ends_at == 28000
    host = [o for o in outs if o.type == "bt_track" and o.target == "host"][0]
    assert host.payload["audio"] == "play"
```

And a `test_ws.py` integration test: start a blindtest with `max_play_s` small, players join, and assert
the host eventually receives a `bt_audio` `pause` (auto-pause) **without the test hanging** (use a short
cap and the existing `_read_until` helper; keep within pytest-timeout=30). Also assert a `replay_bt`
host action produces a fresh `bt_track`.

- [ ] **Step 2: Run to verify they fail** — FAIL.
- [ ] **Step 3: Implement** engine functions + `main.py` wiring.
- [ ] **Step 4: Run** — full `uv run pytest -q` → PASS, NO HANG; ruff clean.
- [ ] **Step 5: Checkpoint** — tick Task 3. **Backend done.**

---

### Task 4: Frontend — types + reducer + `useSpotifyPlayer.setVolume`

**Files:**
- Modify: `frontend/lib/types.ts` (`BlindtestState`/track-now gains `startsAt`, `endsAt`, `maxPlayMs`)
- Modify: `frontend/lib/useGameSocket.ts` (`bt_track` reducer carries `starts_at`/`ends_at`/`max_play_ms`;
  reset/freeze on `buzz_locked` BUZZED and `reveal`)
- Modify: `frontend/lib/useSpotifyPlayer.ts` (add `volume`, `setVolume`)

**Interfaces — Produces:**
- `BlindtestState` gains `startsAt: number; endsAt: number; maxPlayMs: number;` (defaults 0 in
  `EMPTY_BLINDTEST`). The `bt_track` reducer sets them from `p.starts_at`/`p.ends_at`/`p.max_play_ms`.
- `useSpotifyPlayer` return gains `volume: number; setVolume: (v: number) => void;` — calls
  `playerRef.current?.setVolume(v)`, stores `v` in a ref + state, applies it on (re)connect.

- [ ] **Step 1: Implement** the type + reducer + hook changes.
- [ ] **Step 2: Build** — `cd frontend && npm run build` → green.
- [ ] **Step 3: Checkpoint** — tick Task 4.

---

### Task 5: Frontend — host config settings row + start payload

**Files:**
- Modify: `frontend/app/host/[code]/page.tsx` (blindtest config: settings row + `startBlindtest` payload)
- Modify: `frontend/components/BlindtestEditor.tsx` only if the settings live inside it (prefer the host
  page, next to the Démarrer button, mirroring the QCM settings row)

**Interfaces — Produces:**
- New host state `btSettings = { maxPlayS: number; randomStart: boolean; countdown: boolean }`
  (defaults `{ maxPlayS: 30, randomStart: false, countdown: true }`).
- A settings row (max play time number input in seconds, random-start checkbox, countdown checkbox).
- `startBlindtest()` sends `action("set_blindtest_tracks", { tracks: btTracks, max_play_s,
  random_start, countdown })` then `action("start_blindtest")`.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Build** — green.
- [ ] **Step 3: Checkpoint** — tick Task 5.

---

### Task 6: Frontend — `BlindtestStage` countdown/deferred play + progress + volume + replay

**Files:**
- Modify: `frontend/components/BlindtestStage.tsx`

**Behavior:**
- **Deferred play:** the audio effect, when `bt.audio === "play"` and `bt.track`, compares now vs
  `bt.startsAt`. If `bt.startsAt > Date.now()`, show a 3-2-1 countdown and schedule `spotify.play(uri,
  start_ms)` at `startsAt` (a `setTimeout`, cleared on change); else play immediately. Track the
  last-played uri via the existing ref so a re-render doesn't replay.
- **Countdown overlay:** when `Date.now() < bt.startsAt`, show the remaining seconds (reuse the
  `Countdown` component pointing at `startsAt`, or a small local ticker).
- **Progress bar:** when `bt.maxPlayMs > 0` and playing, a bar filling over `[startsAt, endsAt]`.
- **Volume slider:** `<input type="range">` bound to `spotify.volume` → `spotify.setVolume`.
- **Replay button:** `action("replay_bt")`.
- Keep all existing controls (Lecture/Pause/Rejouer, validation, reveal/next) intact.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Build** — green.
- [ ] **Step 3: Checkpoint** — tick Task 6.

---

### Task 7: Frontend — player + TV countdown + progress bar

**Files:**
- Modify: `frontend/app/play/[code]/page.tsx` (blindtest branch)
- Modify: `frontend/app/tv/[code]/page.tsx` (blindtest branch)

**Behavior:** in the blindtest BUZZER_OPEN view, when `Date.now() < bt.startsAt` show the 3-2-1
countdown (big), and once playing show a synced progress bar over `[startsAt, endsAt]` when
`bt.maxPlayMs > 0`. No audio (host only). Reuse the same small countdown/progress approach as the host.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Build** — green.
- [ ] **Step 3: Checkpoint** — tick Task 7. **Phase done. Manual live smoke test = user.**

---

## Self-Review

- **Spec coverage:** A stop-audio (T3 reveal/to_scoreboard pause), B random start (T2), C max play +
  auto-pause (T1 config, T2 timing, T3 timer + on_play_timeout), D volume (T4 hook, T6 slider),
  E countdown (T2 started_at + buzz gate, T6 host deferred play, T7 player/tv), F replay (T3 engine +
  main route, T6 button), G progress bar (T4 state, T6 host, T7 player/tv). All mapped.
- **Placeholder scan:** backend tasks carry real tests + interfaces; frontend tasks are build-gated
  (no FE test runner) with exact files + behavior — not placeholders.
- **Type consistency:** `bt_play_started_at`/`bt_play_ends_at`/`bt_max_play_ms` (backend) ⇄
  `startsAt`/`endsAt`/`maxPlayMs` (frontend) used consistently; `replay_bt` action name matches in
  engine `replay`, `main.py` route, and the host button; `on_play_timeout` referenced by `main.py`
  matches its definition in `blindtest.py`.
