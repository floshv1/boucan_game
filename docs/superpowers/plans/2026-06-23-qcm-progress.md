# QCM Mode — Progress Ledger

Plan: `docs/superpowers/plans/2026-06-23-qcm-mode.md`
Execution: subagent-driven, **no git** (file-based checkpoints, not commits).

## Status
- Task 1 (QCM model + set_qcm_rounds): complete (review clean, 34 tests green)
- Task 2 (start_qcm + load_question): complete (review clean, 36 tests green)
- Task 3 (answer_submit + all_answered): complete (review clean, 39 tests green)
- Task 4 (reveal + scoring): complete (review clean, 45 tests green; minor: reveal_payload extracted for 120-col)
- Task 5 (scoreboard + next_ + state_sync): complete (review clean, 48 tests green; minor: podium-exclusion not strictly asserted in test)
- Task 6 (WS wiring + timer): complete (49 tests green, ruff clean). REGRESSION FOUND & FIXED:
  "reveal"/"skip"/"next" action names collide with the buzzer flow; Task 6 routed them
  unconditionally to qcm → buzzer reveal/next did nothing → test_ws hung on receive_json.
  Fix: route shared actions by session.mode (QCM_ONLY_ACTIONS vs QCM_SHARED_ACTIONS) in
  main.py. Added pytest-timeout (timeout=30) so future hangs fail fast with a stack dump.
- Task 7 (frontend types + reducer): complete (review clean, npm build green, 6 routes)
- Task 8 (host config + QCM editor): complete (review clean, npm build green; minor: no disabled on "Démarrer le QCM")
- Task 9 (host in-game QCM panel): complete (review clean, npm build green, 7 routes)
- Task 10 (player QCM view): complete (review clean, npm build green; §16 ok — correct hidden pre-reveal)
- Task 11 (TV QCM view): complete (review clean, npm build green; §16 ok — TV never shows correct pre-reveal)
- Task 12 (full verification): complete — backend 49 tests + ruff green; frontend build green (7 routes); README updated. Live Docker/browser smoke left for the user to run manually.

## Final whole-branch review (opus) + fixes
Review caught a CRITICAL bug the 12 per-task reviews missed:
- C1 (CRITICAL, FIXED): host page gated on buzzer `round.state`, but QCM never emits `round_state`
  → host stuck on config screen, game unrunnable. Fix: `showConfig` derived from `snapshot.qcm`
  (host/[code]/page.tsx).
- I1 (IMPORTANT, FIXED): reconnect mid-question lost the player's locked answer. Fix: `my_choice`
  in `state_sync_payload` (player_id param) + reducer restores `myChoice`. +1 unit test.
- M1 (MINOR, FIXED): "Démarrer le QCM" now disabled when no valid question.
- I2 (IMPORTANT, DEFERRED): reconnect during REVEAL/SCOREBOARD shows an empty screen until the
  next host action (state_sync doesn't carry reveal/scoreboard data). Self-heals on next click;
  recompute-on-reconnect is more involved. Revisit if it bites in real play.
Verified after fix: backend 50 tests + ruff green; frontend build green.
Security (§16), state-machine routing, timer, scoring, payload contract all verified clean.

## Minor findings (for final review triage)
- T1: `_parse_round` silently truncates >4 choices (defensive; spec says exactly 4).
- T1: `int(item.get("time_limit") or 20)` treats explicit `0` as falsy → 20 (clamped to ≥5 anyway); same for points. Harmless.
- T1: `set_qcm_rounds` also emits a benign `player_list` broadcast (mirrors engine.set_rounds); not in Produces list, carries no secret.
