"""HTTP endpoints for question-pack CRUD + import/export (Phase 4).

Packs are persisted as flat JSON files by ``game/packs_store.py`` — the app's
first on-disk state (everything else is in-memory, cahier §15). Pack files carry
answers, so they are host/editor-side only and never pushed to players/tv.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from game import packs_store

router = APIRouter()

_NOT_FOUND = {"error": "not_found", "detail": "Pack introuvable."}

_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
_IMAGE_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


@router.get("/packs")
async def list_packs() -> dict:
    return {"packs": packs_store.list_packs()}


@router.get("/packs/{pack_id}", response_model=None)
async def get_pack(pack_id: str) -> dict | JSONResponse:
    pack = packs_store.get_pack(pack_id)
    if pack is None:
        return JSONResponse(status_code=404, content=_NOT_FOUND)
    return pack


@router.post("/packs", response_model=None)
async def create_pack(pack: dict) -> dict | JSONResponse:
    # A create always gets a fresh id/timestamps — strip any the client sent.
    data = {k: v for k, v in pack.items() if k not in ("id", "created_at", "updated_at")}
    try:
        return packs_store.save_pack(data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_pack", "detail": str(exc)})


@router.put("/packs/{pack_id}", response_model=None)
async def update_pack(pack_id: str, pack: dict) -> dict | JSONResponse:
    if packs_store.get_pack(pack_id) is None:
        return JSONResponse(status_code=404, content=_NOT_FOUND)
    try:
        return packs_store.save_pack({**pack, "id": pack_id})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_pack", "detail": str(exc)})


@router.delete("/packs/{pack_id}")
async def delete_pack(pack_id: str) -> dict:
    return {"deleted": packs_store.delete_pack(pack_id)}


@router.get("/packs/{pack_id}/export", response_model=None)
async def export_pack(pack_id: str) -> JSONResponse:
    pack = packs_store.get_pack(pack_id)
    if pack is None:
        return JSONResponse(status_code=404, content=_NOT_FOUND)
    # Content-Disposition filename must be ASCII (RFC 6266); strip accents/quotes.
    raw = str(pack.get("name") or "pack")
    safe_name = "".join(c for c in raw if c.isascii() and c not in '"\\/\r\n').strip() or "pack"
    return JSONResponse(
        content=pack,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
    )


@router.post("/packs/import", response_model=None)
async def import_pack(pack: dict) -> dict | JSONResponse:
    # Import = create a fresh copy (new id/timestamps).
    data = {k: v for k, v in pack.items() if k not in ("id", "created_at", "updated_at")}
    try:
        return packs_store.save_pack(data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_pack", "detail": str(exc)})


@router.post("/media", response_model=None)
async def upload_media(file: UploadFile = File(...)) -> dict | JSONResponse:
    """Upload a question image (png/jpeg/webp, <= 5 MB) → {url: /media/<uuid>.<ext>}."""
    ext = _IMAGE_EXT.get(file.content_type or "")
    if ext is None:
        return JSONResponse(status_code=400, content={"error": "bad_type", "detail": "Image png/jpeg/webp requise."})
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        return JSONResponse(status_code=413, content={"error": "too_large", "detail": "Image > 5 Mo."})
    name = f"{uuid.uuid4().hex}.{ext}"
    (packs_store._media_dir() / name).write_bytes(data)
    return {"url": f"/media/{name}"}
