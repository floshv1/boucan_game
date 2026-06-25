"""Phase 4 — persistent pack storage (file-based, no database).

Packs are stored as JSON files under ``PACKS_DIR`` (env, default ``"packs"``).
All reads/writes are synchronous; this module has no FastAPI dependency.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from game.blindtest import _parse_track
from game.builtin_packs import builtin_summaries, get_builtin
from game.qcm import _parse_round

ALLOWED_MODES = {"buzzer", "qcm", "blindtest"}


# ---------------------------------------------------------------------------
# Directory helpers — resolved at call time so tests can monkeypatch env vars
# ---------------------------------------------------------------------------


def _packs_dir() -> Path:
    p = Path(os.environ.get("PACKS_DIR", "packs"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _media_dir() -> Path:
    p = Path(os.environ.get("MEDIA_DIR", "media"))
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def _safe_pack_path(pack_id: str) -> Path | None:
    """Return the resolved ``.json`` path for *pack_id*, or None if unsafe."""
    if not pack_id or "/" in pack_id or "\\" in pack_id or ".." in pack_id:
        return None
    base = _packs_dir()
    candidate = (base / f"{pack_id}.json").resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


# ---------------------------------------------------------------------------
# Item normalisers
# ---------------------------------------------------------------------------


def _normalize_buzzer_item(it: dict) -> dict:
    return {
        "question": str(it.get("question") or ""),
        "answer": str(it.get("answer") or ""),
        "points": max(1, int(it.get("points") or 1)),
        "bonus": bool(it.get("bonus")),
        "image": (str(it["image"]) if it.get("image") else None),
    }


def _normalize_qcm_item(it: dict) -> dict:
    rnd = _parse_round(it)
    d = asdict(rnd)
    d["image"] = str(it["image"]) if it.get("image") else None
    return d


def _normalize_blindtest_item(it: dict) -> dict:
    track = _parse_track(it)
    return {
        "spotify_track_id": track.spotify_track_id,
        "uri": track.uri,
        "title": track.title,
        "artist": track.artist,
        "cover_url": track.cover_url,
        "duration_ms": track.duration_ms,
        "start_ms": track.start_ms,
        "points_title": track.points_title,
        "points_artist": track.points_artist,
        "bonus": track.bonus,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_pack(data: dict) -> dict:
    """Return a normalised pack dict or raise ``ValueError``."""
    mode = data.get("mode")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid mode {mode!r}. Must be one of {ALLOWED_MODES}.")

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Pack name must be a non-empty string.")

    description = str(data.get("description") or "")

    raw_tags = data.get("tags") or []
    tags = [t for t in raw_tags if isinstance(t, str)]

    raw_items = data.get("items") or []
    if mode == "buzzer":
        items = [_normalize_buzzer_item(it) for it in raw_items]
    elif mode == "qcm":
        items = [_normalize_qcm_item(it) for it in raw_items]
    else:  # blindtest
        items = [_normalize_blindtest_item(it) for it in raw_items]

    return {
        "name": name,
        "description": description,
        "tags": tags,
        "mode": mode,
        "items": items,
    }


def list_packs() -> list[dict]:
    """Return summary dicts for every pack (user packs sorted by ``updated_at``
    descending, then the read-only built-in starter packs)."""
    summaries = []
    for path in _packs_dir().glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                pack = json.load(f)
            summaries.append(
                {
                    "id": pack["id"],
                    "name": pack["name"],
                    "mode": pack["mode"],
                    "count": len(pack.get("items", [])),
                    "tags": pack.get("tags", []),
                    "updated_at": pack["updated_at"],
                    "builtin": False,
                }
            )
        except Exception:  # noqa: BLE001
            continue
    summaries.sort(key=lambda s: s["updated_at"], reverse=True)
    return summaries + builtin_summaries()


def get_pack(pack_id: str) -> dict | None:
    """Return the full pack dict, or None if not found / path unsafe."""
    builtin = get_builtin(pack_id)
    if builtin is not None:
        return builtin
    path = _safe_pack_path(pack_id)
    if path is None or not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def save_pack(data: dict) -> dict:
    """Validate, assign id/timestamps, atomically write, and return the saved dict."""
    normalised = validate_pack(data)

    now_iso = datetime.now(UTC).isoformat()

    existing_id = data.get("id")
    if existing_id and get_builtin(existing_id):
        existing_id = None  # never overwrite a built-in; save as a new user pack
    existing_path = _safe_pack_path(existing_id) if existing_id else None

    if existing_id and existing_path and existing_path.exists():
        # Update: preserve id and created_at from the stored file
        with existing_path.open(encoding="utf-8") as f:
            stored = json.load(f)
        pack_id = existing_id
        created_at = stored.get("created_at", now_iso)
    else:
        pack_id = uuid.uuid4().hex
        created_at = now_iso

    full = {
        "id": pack_id,
        "created_at": created_at,
        "updated_at": now_iso,
        **normalised,
    }

    dest = _packs_dir() / f"{pack_id}.json"
    tmp = dest.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    os.replace(tmp, dest)

    return full


def delete_pack(pack_id: str) -> bool:
    """Delete pack file; return True if it existed, False otherwise."""
    path = _safe_pack_path(pack_id)
    if path is None or not path.exists():
        return False
    path.unlink()
    return True
