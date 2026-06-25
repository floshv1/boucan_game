# Blindtest v2 — Progress Ledger

Plan: `docs/superpowers/plans/2026-06-24-blindtest-v2.md`. Spec: `docs/superpowers/specs/2026-06-24-blindtest-v2-design.md`.
Execution: subagent-driven, **NO git** (file briefs/reports in scratchpad, reviewers read changed files, ledger not commits).

## Global constraints (reviewer lens)
- NO git. ruff 120 (E/F/W/I/UP) + pytest green, **pytest-timeout=30 (no hangs)**. Frontend gate `npm run build`.
- §16 unchanged: timing/countdown/progress carry NO answers; title/artist/cover/uri + random start_ms stay host-only until REVEAL.
- A game is 1 mode; don't change buzzer/QCM logic. Blindtest timer reuses `_qcm_timers` slot.
- Defaults: max_play 30000ms (0=no cap), countdown 3000ms, random_start False.

## Tasks
- Task 1 (Session timing fields + config intake) — **complete** (subagent DONE; +2 tests, 140 passed, ruff clean; self-reviewed inline: 5 fields + keyword config match brief, defaults 30000/3000/False, §16 untouched, existing callers unaffected)
- Task 2 (load_track countdown/random/timing payload + on_buzz gate) — **complete** (subagent DONE, verified on disk; +5 tests, 145 passed, ruff clean; now-aware load_track/start/cont/next_, random within bounds, timing to all + start_ms host-only §16, buzz gated during countdown, main.py call sites pass now_ms())
- Task 3 (reveal/scoreboard pause + on_play_timeout + replay + main.py timer wiring) — **complete** (subagent DONE, verified on disk; +6 tests incl. WS integration, 151 passed, no hang, ruff clean; reveal+to_scoreboard append _audio pause, on_play_timeout/replay added, _sync_blindtest_timer reuses _qcm_timers, wired after blindtest buzz + host_action). **Backend done.**
- Task 4 (frontend types + reducer + useSpotifyPlayer.setVolume) — **complete** (subagent DONE; startsAt/endsAt/maxPlayMs in BlindtestState+EMPTY+bt_track/state_sync reducer; useSpotifyPlayer volume/setVolume clamped + re-applied on ready; build green)
- Task 5 (frontend host config settings row + start payload) — **complete** (subagent DONE; btSettings state, settings row (max time / random / countdown) in blindtest config, startBlindtest sends max_play_s/random_start/countdown; build green)
- Task 6 (frontend BlindtestStage countdown/deferred play + progress + volume + replay) — **complete** (subagent DONE; 250ms ticker, deferred play via playTimerRef at startsAt, 3-2-1 overlay, progress bar, volume slider, "Rejouer du début" → play+replay_bt; existing controls intact; build green)
- Task 7 (frontend player + TV countdown + progress bar) — **complete** (subagent DONE; new `BlindtestTimerBar` (own ticker, 3-2-1 + progress) wired into player + TV blindtest branches; build green)
- Final whole-branch review — **complete (inline)**: backend 151 passed + ruff clean; frontend build clean (7 routes). §16 re-audited (timing non-secret, start_ms/title/artist/cover host-only); timer reuses _qcm_timers, cancels on state exit, no hang; buzzer/QCM untouched. **Only remaining = user's live Spotify smoke test.**

## Minor findings (final-review triage)
- BT2-M1: host has both "Rejouer" (seek+resume) and "Rejouer du début" (play+replay_bt) — slight redundancy, both kept intentionally (per brief). Low.
- BT2-M2: `replay_bt` re-emits `bt_track` (same uri) which the host audio effect ignores (uri unchanged → no double-play); the host plays directly on click. Correct but relies on the uri-unchanged guard. Note for the live test.

## Minor findings (final-review triage)
(none yet)
