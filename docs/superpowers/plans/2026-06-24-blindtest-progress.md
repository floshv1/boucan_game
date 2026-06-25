# Blindtest (Spotify) — Progress Ledger

Plan: `C:\Users\flori\.claude\plans\faisons-la-phase-1-fizzy-fountain.md` (Phase 3).
Execution: subagent-driven, **no git** (file-based briefs/reports + this ledger, not commits).

## Tasks (11 plan steps grouped into 6 dispatches)
- Task A (backend: models + `game/blindtest.py` engine + unit tests) — plan §1, §2, §5(engine): **complete** (review SPEC ✅/Approved; 2 Important fixes applied — cont resets revealed, validate(F,F) no-op; 91 passed, ruff clean)
- Task B (backend: `game/spotify_client.py` + `routers/spotify.py` + tests) — plan §3, §5(spotify): **complete** (review SPEC ✅/Approved, no Critical/Important; 116 passed, ruff clean; live OAuth = user smoke test)
- Task C (backend: `main.py` WS wiring + integration tests) — plan §4, §5(ws): **complete** (review SPEC ✅/Approved, no Critical/Important; 117 passed, ruff clean). **Backend done.**
- Task D (frontend: types + reducer + `useSpotifyPlayer` hook) — plan §6, §7, §8: **complete** (review SPEC ✅/Approved, no Critical/Important; build clean, 7 routes)
- Task E (frontend: host config + in-game blindtest panel) — plan §9: **complete** (BlindtestEditor + BlindtestStage + lib/backend.ts + host page wiring; `npm run build` green, 7 routes; self-reviewed: §16 ok (host-only), audio effect via lastUriRef correct, all actions wired)
- Task F (frontend: player + TV blindtest views) — plan §10, §11: **complete** (player blindtest branch in `app/play/[code]/page.tsx`: big Buzzer driven by `blindtest.state`+`snapshot.buzz`, reveal ✓/✗ + cover/title/artist, scoreboard/podium; TV blindtest branch in `app/tv/[code]/page.tsx`: masked "?" cover until REVEAL, buzz order, classement ▲/▼, podium; `npm run build` green; backend 118 passed)
- **Backend fix (F):** `_bt_track_outbounds` now also emits `buzz_locked` (`engine.buzz_payload`) to "all" so host/player/tv reset their buzz queue/floor/state on each track (load_track/cont reset server-side but emitted no round_state). Regression test `test_load_track_emits_buzz_locked_resetting_clients` added.
- **Live smoke test (user, on Docker): PASSED ✅** — blindtest plays, buzz auto-pauses, reveal works. Fixes made live during the test:
  - Spotify **Development Mode** limits: search `limit` capped at 10 (was 12 → 400 "Invalid limit"); `/playlists/{id}/tracks` is 403 → switched to the playlist-**object** endpoint `/v1/playlists/{id}` and parse both standard (`tracks.items`/`item.track`) and partner (`items.items`/`item.item`) shapes; `/browse/*` and editorial playlists 403/404 (use own playlists).
  - SDK auth needed scopes **`user-read-email` + `user-read-private`** (not just `streaming`) → added; `show_dialog=true` forces re-consent so they're actually granted; `exchange_code` logs granted scopes.
  - Router catches `httpx.HTTPStatusError` → clean JSON (no more 500-without-CORS = "Erreur réseau").
  - Frontend: `useSpotifyPlayer.play()` checks response + retries once on 404 (device-not-propagated); `BlindtestStage` audio effect gated on `spotify.ready` (kills the "no list was loaded" race).
  - `_bt_track_outbounds` emits `buzz_locked` so host/player/tv reset buzz state per track.
  - `compose.yml`: backend `env_file: ./backend/.env` (Spotify creds in container).
  - **Root cause of the final "Authentication failed" / "Failed to initialize player": browser ad/tracker blockers** (Opera GX built-in blocker, Firefox Enhanced Tracking Protection) blocking the SDK's third-party requests to `apresolve.spotify.com` / `spclient.wg.spotify.com` / `dealer.g2.spotify.com`. Fix = disable the blocker for the host site, or use plain Chrome/Edge. See [[spotify-blindtest-gotchas]].
- Final whole-branch review (opus): **complete** (inline). §16 re-audited end-to-end: only `reveal` (REVEAL state, "all") carries title/artist/cover; `_track_payload` secrets gated by `include_track` (host-only at both call sites — `_bt_track_outbounds`, `state_sync_payload`); `prepared_blindtest` host-only; new `buzz_locked` carries no secrets. Frontend player/tv never read `blindtest.track` (null for them), only `blindtest.reveal` at REVEAL. Backend 118 passed + ruff clean; `npm run build` green (7 routes). **Only remaining step = user's live Spotify smoke test.**

## Global constraints (reviewer attention lens)
- **§16**: `title`/`artist`/`cover_url` NEVER sent to `player`/`tv` roles before REVEAL state.
  `prepared_blindtest` (carries answers) is host-only. WS target "players" includes tv spectators.
- **No DB / in-memory only** (cahier §15), including Spotify tokens (module-level, re-auth on reboot).
- **No git commands.**
- Mode separation: a game is 100% buzzer OR qcm OR blindtest; buzzer/qcm logic untouched.
- Reuse: `engine.buzz`/`engine.invalidate` (arbitration), `qcm.to_scoreboard`/`qcm.game_end_payload`
  (scoreboard/podium). Audio directive (`play`/`pause`) only in host-targeted payloads.

## Minor findings (final-review triage)
- B-M1: `_parse_playlist_id` bare-id branch accepts any string without `/`/`:` (no charset guard). Low risk (Spotify 404s a bad id).
- B-M2: `test_exchange_code_stores_tokens` parses POST body with naïve `split("=")`; `urllib.parse.parse_qs` would be safer (passes today).
- B-M3: `test_build_authorize_url_contains_all_params` uses substring `in` checks rather than parsed key-value assertions.
- D-M1: `types/spotify.d.ts` has a misplaced `eslint-disable-next-line` comment (targets `export {}` instead of the `any`); cosmetic.
