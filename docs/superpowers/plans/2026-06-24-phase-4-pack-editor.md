# Phase 4 — Éditeur de packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a web pack editor so the host can author, persist, import/export, and load reusable per-mode question packs (buzzer / QCM / blindtest), with image upload for QCM/buzzer questions.

**Architecture:** Flat JSON files (one pack per file in `packs/`, images in `media/`) behind a `routers/packs.py` + `game/packs_store.py`. Per-mode packs map 1:1 onto existing draft shapes and the proven start flow — no engine rework. A new `/editor` route manages the library and reuses existing editor components; the host page gains additive "Charger un pack" / "Enregistrer comme pack".

**Tech Stack:** Backend FastAPI + uv + ruff + pytest. Frontend Next.js 15 / React 19 / TS strict.

## Global Constraints

- **NO git commands** — never run git. Checkpoints update the ledger, not commits.
- Backend: `ruff check` + `ruff format --check` clean (line-length 120, select E/F/W/I/UP). `pytest` green (asyncio_mode=auto, pytest-timeout=30). Run via `uv run`.
- Frontend: TS strict; gate = `npm run build` (no FE test runner). No eslint errors.
- **§15**: live game state stays 100% in-memory. `packs/` + `media/` are the ONLY persistent state.
- **§16**: a question `image` is part of the PROMPT (shown during the question), never an answer — it MAY go to players/tv. Pack files (which carry answers) are host/editor-side only; never sent to players/tv.
- Per-mode packs only; a game is 100% one mode. Do NOT change buzzer/QCM/blindtest game logic except to thread the new `image` field.
- Reuse: `lib/backend.ts` `backendHttpUrl`, components `QcmEditor`/`BlindtestEditor`, the `/api/:path*` Next rewrite pattern.
- Spotify dev-mode constraints still apply to blindtest authoring — see `docs/.../2026-06-24-blindtest-progress.md`.

**Ledger:** create `docs/superpowers/plans/2026-06-24-phase-4-progress.md` (mirror the blindtest ledger) and tick tasks there at each checkpoint. No commits.

---

### Task 1: Backend — `game/packs_store.py` (file storage + validation)

**Files:**
- Create: `backend/game/packs_store.py`
- Test: `backend/tests/test_packs_store.py`

**Interfaces:**
- Produces:
  - `PACKS_DIR` / `MEDIA_DIR` resolved from env (`PACKS_DIR` default `packs`, `MEDIA_DIR` default `media`), relative to backend CWD; `_packs_dir()`/`_media_dir()` create the dir on demand.
  - `ALLOWED_MODES = {"buzzer", "qcm", "blindtest"}`
  - `validate_pack(data: dict) -> dict` — returns a normalized pack dict or raises `ValueError`. Enforces `mode in ALLOWED_MODES`, `name` non-empty str, `tags` list[str], `items` list; normalizes each item per mode (see below); drops unknown top-level keys.
  - `list_packs() -> list[dict]` — `[{id, name, mode, count, tags, updated_at}]`, sorted by `updated_at` desc.
  - `get_pack(pack_id: str) -> dict | None` — full pack or None.
  - `save_pack(data: dict) -> dict` — validates; assigns `id` (uuid4 hex) + `created_at` if absent, always refreshes `updated_at` (ISO-8601 UTC); atomic write (`<id>.json.tmp` → `os.replace`); returns the saved pack.
  - `delete_pack(pack_id: str) -> bool`
- Item normalization (per mode), reusing existing parse rules:
  - `buzzer`: `{question:str, answer:str, points:int>=1, image:str|None}`
  - `qcm`: `{question:str, choices:list[str] padded/truncated to 4, correct:int 0..3, time_limit:int>=5, points:int>=1, image:str|None}`
  - `blindtest`: `{spotify_track_id, uri, title, artist, cover_url, duration_ms, start_ms, points_title, points_artist}` (ints clamped >=0; no image)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_packs_store.py
import json
import pytest
from game import packs_store


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PACKS_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))


def test_save_assigns_id_and_timestamps_and_roundtrips():
    saved = packs_store.save_pack(
        {"name": "Soirée", "mode": "qcm", "tags": ["musique"],
         "items": [{"question": "Q", "choices": ["a", "b", "c", "d"], "correct": 1, "points": 1000}]}
    )
    assert saved["id"] and saved["created_at"] and saved["updated_at"]
    got = packs_store.get_pack(saved["id"])
    assert got["name"] == "Soirée"
    assert got["items"][0]["correct"] == 1
    assert got["items"][0]["image"] is None


def test_list_returns_summaries_sorted():
    a = packs_store.save_pack({"name": "A", "mode": "buzzer", "items": [{"question": "x", "answer": "y", "points": 1}]})
    b = packs_store.save_pack({"name": "B", "mode": "qcm", "items": []})
    summaries = packs_store.list_packs()
    assert {s["id"] for s in summaries} == {a["id"], b["id"]}
    assert summaries[0]["count"] == 0 or summaries[0]["count"] == 1
    assert "correct" not in summaries[0]  # summary only


def test_validate_rejects_bad_mode():
    with pytest.raises(ValueError):
        packs_store.validate_pack({"name": "x", "mode": "texte", "items": []})


def test_validate_rejects_empty_name():
    with pytest.raises(ValueError):
        packs_store.validate_pack({"name": "", "mode": "qcm", "items": []})


def test_qcm_item_normalized_to_four_choices():
    saved = packs_store.save_pack({"name": "x", "mode": "qcm",
        "items": [{"question": "q", "choices": ["a"], "correct": 9}]})
    item = packs_store.get_pack(saved["id"])["items"][0]
    assert len(item["choices"]) == 4
    assert item["correct"] == 0


def test_delete_removes_pack():
    saved = packs_store.save_pack({"name": "x", "mode": "qcm", "items": []})
    assert packs_store.delete_pack(saved["id"]) is True
    assert packs_store.get_pack(saved["id"]) is None
    assert packs_store.delete_pack("nope") is False
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_packs_store.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement `game/packs_store.py`** — module-level functions; `os.environ.get("PACKS_DIR", "packs")`, `pathlib.Path`, `uuid.uuid4().hex`, `datetime.now(UTC).isoformat()`, atomic `os.replace`. Mode item normalizers may import `qcm._parse_round` / `blindtest._parse_track` and serialize their dataclasses back to dicts (add the `image` field for qcm/buzzer in Task 2; for now store `image=item.get("image") or None`). `list_packs` reads each `*.json`, returns summaries with `count=len(items)`.

- [ ] **Step 4: Run tests** — `uv run pytest tests/test_packs_store.py -q` → PASS. Then `uv run ruff check game/packs_store.py tests/test_packs_store.py` and `uv run ruff format --check` → clean.

- [ ] **Step 5: Checkpoint** — full suite `uv run pytest -q` green; tick Task 1 in the ledger (no git).

---

### Task 2: Backend — add `image` to QCM + buzzer models, thread through payloads

**Files:**
- Modify: `backend/game/models.py` (`QcmRound`, `PreparedRound` add `image: str | None = None`; `Session` add `image: str | None = None` for the live buzzer round)
- Modify: `backend/game/qcm.py` (`_parse_round`, `prepared_qcm_payload`, `question_start_payload`)
- Modify: `backend/game/engine.py` (`set_rounds` parse, `_prepared_rounds_outbound`, `round_state_payload`, `_open_round`/`_open_round` signature to carry image)
- Test: extend `backend/tests/test_qcm.py` and `backend/tests/test_engine.py` (or the buzzer test file)

**Interfaces:**
- Produces: `QcmRound.image`, `PreparedRound.image`, `Session.image`; `question_start` payload includes `"image"` (host AND players — it's the prompt); `prepared_qcm`/`prepared_rounds` include `"image"`; buzzer `round_state` payload includes `"image"`.

- [ ] **Step 1: Write failing tests** — e.g. in `test_qcm.py`:

```python
def test_question_start_includes_image_for_players():
    session, _ = _lobby_session()  # existing helper
    qcm.set_qcm_rounds(session, [{"question": "q", "choices": ["a","b","c","d"], "correct": 0, "image": "/media/x.webp"}])
    outs = qcm.start_qcm(session, now=0)
    players = [o for o in outs if o.type == "question_start" and o.target == "players"][0]
    assert players.payload["image"] == "/media/x.webp"
```

And in the buzzer test file:

```python
def test_prepared_round_carries_image():
    session = _lobby_session()
    outs = engine.set_rounds(session, [{"question_text": "Q", "answer": "A", "points": 1, "image": "/media/y.webp"}])
    prep = [o for o in outs if o.type == "prepared_rounds"][0]
    assert prep.payload["rounds"][0]["image"] == "/media/y.webp"
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_qcm.py -k image tests/test_engine.py -k image -q` → FAIL (KeyError/no image).

- [ ] **Step 3: Implement** — add `image: str | None = None` to `QcmRound` and `PreparedRound`; `_parse_round` reads `item.get("image") or None`; `prepared_qcm_payload` and `question_start_payload` add `"image": rnd.image`. In `engine.py`: `set_rounds` `PreparedRound(..., image=item.get("image") or None)`; `_prepared_rounds_outbound` dict adds `"image": r.image`; `_open_round(..., image)` sets `session.image = image`; `play_prepared` passes `prepared.image`; `round_state_payload` adds `"image": session.image`; reset paths (`next`/skip) set `session.image = None`.

- [ ] **Step 4: Run tests** — targeted then full `uv run pytest -q` → PASS; ruff clean.

- [ ] **Step 5: Checkpoint** — tick Task 2 in ledger.

---

### Task 3: Backend — `routers/packs.py` CRUD + import/export, mounted in `main.py`

**Files:**
- Create: `backend/routers/packs.py`
- Modify: `backend/main.py` (`from routers.packs import router as packs_router`; `app.include_router(packs_router, prefix="/api")`)
- Test: `backend/tests/test_packs_router.py`

**Interfaces (endpoints, all under `/api`):**
- `GET /api/packs` → `{ "packs": [summary…] }`
- `GET /api/packs/{id}` → full pack or 404 `{error}`
- `POST /api/packs` (body = pack dict) → saved pack; 400 on `ValueError`
- `PUT /api/packs/{id}` (body = pack dict, id in path wins) → saved pack; 404 if missing; 400 on invalid
- `DELETE /api/packs/{id}` → `{deleted: bool}`
- `GET /api/packs/{id}/export` → `JSONResponse` with `Content-Disposition: attachment; filename="<name>.json"`
- `POST /api/packs/import` (body = pack dict) → new pack (id reassigned)

Use `JSONResponse(status_code=…, content={"error": …, "detail": …})` for errors (mirror `routers/spotify.py`), so CORS headers attach.

- [ ] **Step 1: Write failing tests** (offline, `TestClient`, `tmp_path` env via fixture mirroring Task 1):

```python
def test_create_list_get_delete_roundtrip(client):
    r = client.post("/api/packs", json={"name": "P", "mode": "qcm", "items": []})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert any(s["id"] == pid for s in client.get("/api/packs").json()["packs"])
    assert client.get(f"/api/packs/{pid}").json()["name"] == "P"
    assert client.delete(f"/api/packs/{pid}").json()["deleted"] is True
    assert client.get(f"/api/packs/{pid}").status_code == 404


def test_create_invalid_mode_returns_400(client):
    assert client.post("/api/packs", json={"name": "P", "mode": "nope", "items": []}).status_code == 400


def test_export_import_roundtrip(client):
    pid = client.post("/api/packs", json={"name": "P", "mode": "buzzer",
        "items": [{"question": "q", "answer": "a", "points": 1}]}).json()["id"]
    exported = client.get(f"/api/packs/{pid}/export").json()
    imported = client.post("/api/packs/import", json=exported).json()
    assert imported["id"] != pid
    assert imported["items"][0]["answer"] == "a"
```

(`client` fixture: build a bare FastAPI app with `packs_router` under `/api`, or reuse the existing app fixture pattern from `test_spotify_client.py` router tests.)

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_packs_router.py -q` → FAIL.
- [ ] **Step 3: Implement** `routers/packs.py` calling `packs_store`; mount in `main.py`.
- [ ] **Step 4: Run tests** — targeted + full `uv run pytest -q` → PASS; ruff clean.
- [ ] **Step 5: Checkpoint** — tick Task 3.

---

### Task 4: Backend — media (image) upload + static serving

**Files:**
- Modify: `backend/routers/packs.py` (`POST /api/media`)
- Modify: `backend/main.py` (mount `StaticFiles(directory=MEDIA_DIR)` at `/media`, creating the dir first)
- Modify: `backend/pyproject.toml` if `python-multipart` is missing (FastAPI `UploadFile` needs it) — add `python-multipart>=0.0.9`
- Test: extend `backend/tests/test_packs_router.py`

**Interfaces:**
- `POST /api/media` (multipart `file`) → `{ "url": "/media/<uuid>.<ext>" }`; reject non-image content-type (400) and files > 5 MB (413). Allowed: `image/png`→`png`, `image/jpeg`→`jpg`, `image/webp`→`webp`.
- Static: `GET /media/<file>` serves the bytes.

- [ ] **Step 1: Write failing tests**:

```python
def test_media_upload_returns_url_and_serves(client):
    r = client.post("/api/media", files={"file": ("x.png", b"\x89PNG\r\n\x1a\nfake", "image/png")})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/media/") and url.endswith(".png")


def test_media_rejects_non_image(client):
    r = client.post("/api/media", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify they fail** — FAIL.
- [ ] **Step 3: Implement** — `UploadFile`; validate `file.content_type`; read with size cap (read in chunks or `len(await file.read())`); write `<uuid>.<ext>` to `MEDIA_DIR`; return url. Mount `StaticFiles`. Add `python-multipart` dep + `uv sync` if needed.
- [ ] **Step 4: Run tests** — full `uv run pytest -q` → PASS; ruff clean.
- [ ] **Step 5: Checkpoint** — tick Task 4. **Backend done.**

---

### Task 5: Frontend — data layer: `Pack` types, `lib/packs.ts`, `/media` rewrite

**Files:**
- Modify: `frontend/lib/types.ts` (add `image?: string | null` to `QcmRoundDraft` and the buzzer row draft; add `Pack`/`PackSummary` interfaces)
- Create: `frontend/lib/packs.ts`
- Modify: `frontend/next.config.ts` (add `/media/:path*` rewrite)
- Modify: `frontend/components/QcmEditor.tsx` Props comment only if needed (no behavior change here)

**Interfaces:**
- `Pack = { id: string; name: string; description: string; tags: string[]; mode: "buzzer"|"qcm"|"blindtest"; items: unknown[]; created_at: string; updated_at: string }`
- `PackSummary = { id; name; mode; count; tags; updated_at }`
- `lib/packs.ts`: `listPacks()`, `getPack(id)`, `savePack(pack)`, `updatePack(id, pack)`, `deletePack(id)`, `importPack(pack)`, `uploadImage(file): Promise<string>` (POST `/api/media`, returns url) — all via `backendHttpUrl`.
- `next.config.ts` rewrites: append `{ source: "/media/:path*", destination: \`${BACKEND_URL}/media/:path*\` }`.

- [ ] **Step 1: Implement** the types, `lib/packs.ts`, and the rewrite. (No FE test runner — correctness verified by build + later manual.)
- [ ] **Step 2: Build** — `cd frontend && npm run build` → green.
- [ ] **Step 3: Checkpoint** — tick Task 5.

---

### Task 6: Frontend — extract `BuzzerEditor`, generalize `BlindtestEditor` return path

**Files:**
- Create: `frontend/components/BuzzerEditor.tsx` (props `{ rows: BuzzerRowDraft[]; setRows: Dispatch<SetStateAction<BuzzerRowDraft[]>> }`) extracted from the inline buzzer rows in `app/host/[code]/page.tsx`, with an image-upload control per row (calls `uploadImage`, stores url on `row.image`, shows thumbnail).
- Modify: `frontend/components/QcmEditor.tsx` — add per-row image upload (thumbnail + remove) writing `row.image`.
- Modify: `frontend/components/BlindtestEditor.tsx` — replace hardcoded `\`/host/${code}\`` Spotify return path with a `returnTo: string` prop (host passes `/host/<code>`, editor passes `/editor`); keep `code` only if still needed, else drop.
- Modify: `frontend/app/host/[code]/page.tsx` — use the new `BuzzerEditor` in place of the inline rows (behavior identical); pass `returnTo={\`/host/${code}\`}` to `BlindtestEditor`.

- [ ] **Step 1: Implement** the extraction + image controls + returnTo prop.
- [ ] **Step 2: Build** — `npm run build` green; manually confirm the host page still renders buzzer/qcm/blindtest editors unchanged.
- [ ] **Step 3: Checkpoint** — tick Task 6.

---

### Task 7: Frontend — `/editor` route (library + pack editor)

**Files:**
- Create: `frontend/app/editor/page.tsx` (library: list packs via `listPacks`, grouped by mode, with New / Import / Export / Edit / Delete)
- Create: `frontend/app/editor/[id]/page.tsx` (pack editor: name/description/tags + mode-specific authoring reusing `BuzzerEditor`/`QcmEditor`/`BlindtestEditor`; Save → `savePack`/`updatePack`). New-pack flow: `/editor/new?mode=qcm` or a create-then-redirect; pick whichever is simpler with the App Router.

**Notes:**
- Reuse the visual language already used across host (`bg-volt`, `bg-panel`, chunky shadow buttons, `font-display`, etc.).
- Blindtest authoring needs Spotify connected (reuse `BlindtestEditor` with `returnTo="/editor/<id>"`).
- Map pack `items` ⇄ the editor draft state per mode (the shapes already match the drafts).

- [ ] **Step 1: Implement** the two routes.
- [ ] **Step 2: Build** — `npm run build` green.
- [ ] **Step 3: Checkpoint** — tick Task 7.

---

### Task 8: Frontend — host integration (Charger un pack / Enregistrer comme pack)

**Files:**
- Modify: `frontend/app/host/[code]/page.tsx`
  - Add a "Charger un pack" picker (filtered to the active `mode`) → `getPack(id)` → `setRows`/`setQcmRows`/`setBtTracks` from `pack.items`.
  - Add "Enregistrer comme pack" in each inline editor area → prompt for a name → `savePack({name, mode, items: <current draft state>})`.
  - Existing start actions untouched.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Build** — `npm run build` green.
- [ ] **Step 3: Checkpoint** — tick Task 8.

---

### Task 9: Frontend — render question image (host in-game / player / TV)

**Files:**
- Modify: `frontend/lib/useGameSocket.ts` (carry `image` into the qcm question state and buzzer `round` state from `question_start` / `round_state` / `state_sync`)
- Modify: `frontend/lib/types.ts` (`image?: string|null` on the qcm question + round shapes)
- Modify: `frontend/app/play/[code]/page.tsx`, `frontend/app/tv/[code]/page.tsx`, `frontend/app/host/[code]/page.tsx` (render `<img src={image}>` when present for QCM + buzzer questions, using the `/media` same-origin path)

- [ ] **Step 1: Implement** the reducer/state carry + the three render surfaces.
- [ ] **Step 2: Build** — `npm run build` green.
- [ ] **Step 3: Checkpoint** — tick Task 9.

---

### Task 10: Docker volumes + env + final verification

**Files:**
- Modify: `compose.yml` (named volumes `packs` and `media` mounted into the backend at the working dir's `packs`/`media`; e.g. `volumes: [packs:/app/packs, media:/app/media]` + top-level `volumes:` block)
- Modify: `backend/.env.example` (document `PACKS_DIR`, `MEDIA_DIR` optional defaults)
- Modify: `cahier`/README note optional.

- [ ] **Step 1: Implement** compose volumes + env docs.
- [ ] **Step 2: Verify** — `docker compose config` valid. Backend `uv run pytest -q` + ruff clean; frontend `npm run build` green.
- [ ] **Step 3: Manual smoke** (user/host browser): `/editor` → create a QCM pack with a question image → host "Charger un pack" → Démarrer → image renders on player + TV → restart backend container → pack + image persist (volume).
- [ ] **Step 4: Checkpoint** — tick Task 10. **Phase 4 done.** Final whole-branch review.

---

## Self-Review

- **Spec coverage:** persistence (T1,T10), per-mode packs (T1,T3), CRUD (T3), import/export (T3), media upload+serve (T4), `image` model+payload (T2), `image` render (T9), `/editor` library+authoring (T5,T6,T7), additive host integration (T8), Docker volumes (T10), `/media` rewrite (T5). All spec sections mapped.
- **Placeholder scan:** backend tasks carry real test + impl guidance; frontend tasks are build-gated with exact files (no FE test runner exists, so "implement + build green" is the correct cycle, not a placeholder).
- **Type consistency:** `image: str|None` (backend) ⇄ `image?: string|null` (frontend) used consistently; `Pack`/`PackSummary` shapes match `packs_store` outputs; `uploadImage`→url→stored on draft `image`→served via `/media` rewrite is consistent end to end.
