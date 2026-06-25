# Phase 4 — Éditeur de packs (Design)

Date: 2026-06-24 · Cahier refs: §7, §10 (Phase 4), §20, §21

## Context

The quiz-app has three working game modes (buzzer, QCM, blindtest), all live-verified.
Today the host types every question fresh in the inline host editors and it is **lost on
restart** (state is 100% in-memory, no DB). Phase 4 adds a **pack editor**: author reusable
question packs, persist them to disk, import/export JSON, and load a pack into a game. This is
the app's **first persistent state**.

Decisions locked during brainstorming:

- **Per-mode packs, single-mode games.** A pack holds one mode's content (a blindtest pack, a
  QCM pack, a buzzer pack). Starting a game loads one pack. Keeps today's "a game is 100% one
  mode" engine with **zero rework**. (Rejected: multi-mode packs / mixed games — a major engine
  rework, deferred.)
- **Editor covers the 3 playable modes** (buzzer, QCM, blindtest). **Texte-libre (§4.4) deferred**
  to its own later mode-phase.
- **Image upload is in scope** for QCM/buzzer questions (extends models + render paths).
- **Additive host integration**: a separate `/editor` manages the library; the host page gains a
  "Charger un pack" picker that fills the existing inline editors (the proven start flow is
  untouched), and inline editors gain "Enregistrer comme pack."
- **Out of scope:** texte-libre mode, blindtest audio-file upload (blindtest stays Spotify-only,
  see [[spotify-blindtest-gotchas]]), multi-mode games.

## Storage

Flat **JSON files**, one pack per file in `packs/`; uploaded images in `media/`. No DB, no index
file — the list endpoint scans the directory. Matches the project's file-based, no-DB ethos and
makes packs trivially shareable/backup-able. (Rejected: a single `packs.json` index — concurrent
-write risk; SQLite — overkill, contradicts the in-memory philosophy.)

**Persistence consequence:** `packs/` and `media/` are the app's first on-disk state. In Docker
they must be **named volumes** in `compose.yml` so they survive rebuilds/restarts. Game state
stays ephemeral.

### Pack JSON schema

```json
{
  "id": "uuid4",
  "name": "Culture générale — Soirée 2025",
  "description": "",
  "tags": ["musique", "cinéma"],
  "mode": "qcm" | "buzzer" | "blindtest",
  "items": [ /* mode-specific draft objects, see below */ ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

`items` reuse the existing draft shapes so loading a pack maps 1:1 onto the start flow:

- **buzzer**: `{ "question": str, "answer": str, "points": int, "image": str|null }`
- **qcm**: `QcmRoundDraft` = `{ question, choices[4], correct, time_limit, points, image: str|null }`
- **blindtest**: blindtest track draft = `{ spotify_track_id, uri, title, artist, cover_url,
  duration_ms, start_ms, points_title, points_artist }` (no uploaded image; `cover_url` from Spotify)

`image` is a relative media URL (e.g. `/media/<uuid>.webp`) or `null`.

## Backend

### `game/packs_store.py` (storage module, unit-testable)
Pure-ish file I/O over a configurable base dir (env `PACKS_DIR`, default `packs/`; `MEDIA_DIR`,
default `media/`). Functions: `list_packs()`, `get_pack(id)`, `save_pack(pack)` (create/update,
sets timestamps + id), `delete_pack(id)`, `validate_pack(dict)` (mode ∈ allowed, items shape per
mode, strips unknown fields). Atomic write (temp file + rename). Tests use `tmp_path`.

### `routers/packs.py` (mounted under `/api`)
- `GET  /api/packs` → list `[{id, name, mode, count, tags, updated_at}]`
- `GET  /api/packs/{id}` → full pack (404 if missing)
- `POST /api/packs` → create (validated) → full pack
- `PUT  /api/packs/{id}` → update (validated)
- `DELETE /api/packs/{id}`
- `GET  /api/packs/{id}/export` → JSON download (Content-Disposition)
- `POST /api/packs/import` → upload a pack JSON (validated, new id assigned)
- `POST /api/media` → multipart image upload; validate content-type (png/jpeg/webp) + size cap
  (e.g. 5 MB); store as `<uuid>.<ext>`; return `{ "url": "/media/<uuid>.<ext>" }`
- Serve `media/` via `StaticFiles` mount at `/media`.

Validation errors → clean 4xx JSON (mirror the spotify router's `JSONResponse` pattern, so CORS
headers are attached and the frontend shows a real message).

### Model changes
Add optional `image: str | None = None` to the **QCM question** and **buzzer round** models and
their prepared/draft payloads. The image is part of the **prompt** (shown during the question),
never an answer → no §16 concern. Wire it through `prepared_qcm`/`question_start` and the buzzer
round payloads so host/player/tv receive it.

## Frontend

### `/editor` (new route `app/editor/`)
- **Library view**: cards grouped by mode (badge), showing name, tags, item count; buttons:
  New (pick mode), Import (file), and per-card Edit / Export / Delete.
- **Pack editor view**: name/description/tags fields + per-mode item authoring that **reuses
  existing components**: `QcmEditor`, `BlindtestEditor`, and a new small `BuzzerEditor` extracted
  from the inline buzzer rows currently in `app/host/[code]/page.tsx`. QCM/buzzer rows gain an
  **image upload control** (`POST /api/media` → store returned url on the item) + thumbnail + per
  -question preview. Save → `POST`/`PUT /api/packs`.
- Data helpers in `lib/packs.ts` (list/get/save/delete/import/export) using `backendHttpUrl`
  (reuse `lib/backend.ts`).

### Host page integration (additive, `app/host/[code]/page.tsx`)
- **"Charger un pack"** picker (filtered to the active mode) → `GET /api/packs/{id}` → fill the
  inline editor state (`setRows` / `setQcmRows` / `setBtTracks`). The existing start actions
  (`set_blindtest_tracks`, prepared_qcm, prepared_rounds) are untouched.
- **"Enregistrer comme pack"** button in each inline editor → `POST /api/packs` from current state.
- Extract `BuzzerEditor` so the host page and `/editor` share one component.

### Image rendering & URL resolution
Show the question image (when present) in the host in-game panel, the player view, and the TV
view, for QCM and buzzer questions. Images are stored/served as `/media/<file>` on the backend
(:8200), but the pages load from :3200 — so add a **Next rewrite** `/media/:path*` →
`${BACKEND_URL}/media/:path*` in `frontend/next.config.ts` (mirroring the existing `/api/:path*`
rewrite). Then `<img src="/media/<file>">` resolves same-origin with no CORS. Upload (`POST
/api/media`) already flows through the existing `/api` rewrite.

## Docker / config
- `compose.yml`: mount named volumes for `packs/` and `media/` on the backend service; add
  `PACKS_DIR`/`MEDIA_DIR` envs if paths differ from defaults.
- `.env.example`: document `PACKS_DIR`, `MEDIA_DIR` (optional, with defaults).

## Verification
- **Backend**: pytest for `packs_store` (CRUD, validation, atomic write via `tmp_path`), the
  router endpoints (import/export round-trip, media upload type/size rejection), and the
  `image` field flowing through qcm/buzzer payloads. `ruff check` + `ruff format --check` clean.
- **Frontend**: `npm run build` green.
- **Manual**: author a QCM pack with a question image in `/editor` → on host "Charger un pack" →
  Démarrer → image renders on player + TV → reveal/scoreboard unaffected. Restart the backend
  container → pack and image still present (volume).

## Out of scope (explicit)
Texte-libre game mode; blindtest audio-file upload; multi-mode/mixed games; pack
versioning/auth/sharing-server; reordering beyond what the existing editors offer.
