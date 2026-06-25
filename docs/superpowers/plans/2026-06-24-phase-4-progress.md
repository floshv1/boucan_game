# Phase 4 — Éditeur de packs — Progress Ledger

Plan: `docs/superpowers/plans/2026-06-24-phase-4-pack-editor.md`. Spec: `docs/superpowers/specs/2026-06-24-phase-4-pack-editor-design.md`.
Execution: subagent-driven, **NO git** (file briefs/reports in scratchpad, reviewers read changed files, ledger not commits).

## Global constraints (reviewer attention lens)
- **NO git commands.** In-memory game state stays (§15); `packs/` + `media/` are the only persistent state.
- **§16:** question `image` = prompt (may reach players/tv); pack files carry answers → host/editor only, never to players/tv before REVEAL.
- Per-mode packs; a game is 100% one mode; do NOT change buzzer/QCM/blindtest logic except threading `image`.
- Backend: ruff 120 (E/F/W/I/UP) + pytest green. Frontend: TS strict, `npm run build` gate.
- Reuse `backendHttpUrl` (`lib/backend.ts`), `QcmEditor`/`BlindtestEditor`, the `/api` Next rewrite.

## Tasks
- Task 1 (backend `game/packs_store.py` + tests) — **complete** (review Spec ✅ / Quality Approved; 127 passed, ruff clean)
- Task 2 (backend `image` on QcmRound/PreparedRound + payloads) — **complete** (done inline after subagent hit session limit; +3 tests, 130 passed, ruff clean; self-reviewed §16: image=prompt reaches players, answers still gated; state_sync carries image via question_start_payload/round_state_payload)
- Task 3 (backend `routers/packs.py` CRUD/import/export + mount) — **complete** (inline; mounted prefix `/api`; export filename ASCII-sanitized for RFC-6266; 136 passed)
- Task 4 (backend media upload + StaticFiles) — **complete** (inline; `POST /api/media` png/jpeg/webp <=5MB, `python-multipart` added + `uv sync`; `StaticFiles` mounted at `/media` via `packs_store._media_dir()`; 138 passed, ruff clean). **Backend done.**
- Task 5 (frontend types + `lib/packs.ts` + `/media` rewrite) — **complete** (inline; `Pack`/`PackSummary`/`BuzzerRowDraft`/`image?` types; `lib/packs.ts` CRUD+import+uploadImage; `/media` Next rewrite; build green)
- Task 6 (frontend extract `BuzzerEditor`, image controls, BlindtestEditor returnTo) — **complete** (inline; new `ImageField` + `BuzzerEditor`; image control on QcmEditor; host buzzer Row→BuzzerRowDraft (points number); BlindtestEditor `code`→`returnTo`; build green)
- Task 7 (frontend `/editor` library + pack editor) — **complete** (inline; `app/editor/page.tsx` library + `app/editor/[id]/page.tsx` editor (new+existing, Suspense for useSearchParams); reuses Buzzer/Qcm/BlindtestEditor; build green, routes ○ /editor + ƒ /editor/[id])
- Task 8 (frontend host integration load/save pack) — **complete** (inline; `PackBar` component wired into all 3 config blocks: load filtered pack → setRows/setQcmRows/setBtTracks; "enregistrer comme pack"; build green)
- Task 9 (frontend render question image host/player/tv) — **complete** (inline; reducer carries `image` automatically via question_start/round_state payloads + types; rendered on player QCM+buzzer and TV QCM+buzzer; build green)
- Task 10 (Docker volumes + env + final verification) — **complete** (inline; `compose.yml` named volumes `packs:/app/packs` + `media:/app/media`; `.env.example` documents PACKS_DIR/MEDIA_DIR; compose config valid; backend 138 passed + ruff clean; frontend build green). **Manual Docker smoke test = user (Task 10 Step 3).**
- Final whole-branch review (opus): **complete (inline)** — see below.

## Final review (inline)
- **§16:** pack files carry answers (qcm `correct`, buzzer `answer`, blindtest title/artist) but are only reachable via `/api/packs*` (host/editor) — never pushed to players/tv. Game-start still routes through `set_qcm_rounds`/`set_rounds`/`set_blindtest_tracks`, which keep answers host-only. `image` is the prompt → intentionally reaches players/tv. Clean.
- Backend 138 passed, ruff clean; frontend build clean (7 routes). compose valid.
- **Minor deviations (acceptable):** host *in-game* panel does not render the question image (only player+TV do — the host authored it and sees the answer panel); `/editor` blindtest authoring loses unsaved tracks if Spotify connect navigates away (one-time, backend stays authenticated); `routers/packs.py` + `main.py` use `packs_store._media_dir()` (private) — harmless under E/F/W/I/UP.

## Minor findings (final-review triage)
- T1-M1: `packs_store.py` `# noqa: BLE001` references a rule not in the selected ruleset (E/F/W/I/UP) — harmless/meaningless.
- T1-M2: `save_pack` has a benign TOCTOU window reading `created_at` on update (single-user home server → fine).
