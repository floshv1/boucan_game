# Boucan v2 — simpler, lighter, responsive (design)

Date: 2026-06-25
Status: approved (no git commit per repo rule — see memory "no-git-commands")

## Context
Boucan is a real-time party quiz (buzzer / QCM / blindtest). The flow works but
the UI is dense and setup is heavy: hosts must type every question and set points
per blindtest song. Goal: make it minimalist and ergonomic — fast to start, easy
to read on any device — and add a couple of light scoring features.

## Decisions (confirmed)
- **Bonus = ×2 flag.** Host marks specific items as Bonus; they award double.
- **Default bank = QCM + Buzzer** built-in starter packs (FR culture générale).
  No built-in blindtest playlist (needs the host's own Spotify tracks).
- **Blindtest points = two global fields** (`points titre`, `points artiste`)
  applied to every song; per-song point inputs removed.

## A. Scoring
- Add `bonus: bool = False` to `PreparedRound`, `QcmRound`, `BlindtestTrack`
  (`backend/game/models.py`) and to the pack normalisers (`packs_store.py`).
- Doubling when `bonus`:
  - Buzzer `engine.validate`: `score += points * 2`.
  - QCM `qcm`: effective base points doubled before the speed/streak formula.
  - Blindtest `validate`: title/artist awards doubled for that song.
- **Blindtest global points:** add `session.bt_points_title` / `bt_points_artist`,
  set in `set_blindtest_tracks` (from host payload, default 1). `validate` awards
  `bt_points_title`/`bt_points_artist` (×2 if the song is bonus) instead of the
  per-track fields. Per-track point fields stay in the model for pack storage but
  are no longer edited in the UI.
- Reveal `deltas` reflect the doubled values so TV/players show the right gain.
- TV/host show a `⭐︎ ×2` chip on bonus items.

## B. Default question bank
- Ship read-only built-in packs as data in the backend (e.g.
  `backend/game/builtin_packs.py`): 2 QCM packs + 1–2 Buzzer packs, ~10–12 items
  each, stable ids `builtin-<mode>-<slug>`.
- Merge them into `packs_store.list_packs()` / `get_pack()` (built-ins first,
  flagged `builtin: true`, not writable/deletable).
- `PackBar` groups built-ins under "▶ Prêt à jouer" so "load → Démarrer" needs no
  typing.

## C. Editor & host simplification
- Shared compact control primitives (number stepper, ⭐︎ Bonus toggle) to keep
  editors consistent and small.
- Blindtest editor: drop per-song Pts titre/Pts artiste; add a settings row with
  the two global point fields; each song row gets a départ(s) field + ⭐︎ toggle.
- QCM & Buzzer editor rows get a ⭐︎ Bonus toggle.
- Host console: promote the pack picker to the top of each mode; one clear primary
  "Démarrer" button; tightened spacing.

## D. Responsive
- Pass over `app/page.tsx`, `app/host/[code]/page.tsx`, `app/host/page.tsx`,
  `app/play/*`, `app/tv/[code]/page.tsx`, editors: fluid type, wrapping controls,
  ≥44px tap targets, host console stacks to one column on phones, TV scales up on
  large screens. Player stays mobile-first.

## E. Keep / out of scope
- Keep néon identity, equalizer motif, all prior fixes + tests.
- Out: blindtest default playlist, new modes, auth, i18n.

## Verification
- Backend: extend `tests/test_engine.py`, `tests/test_qcm.py`,
  `tests/test_blindtest.py`, `tests/test_packs*` for bonus doubling, blindtest
  global points, and built-in pack listing. Run pytest (pure-logic subset).
- Frontend: `tsc --noEmit` + `next build`. Manual responsive review at phone /
  tablet / desktop / TV widths.
