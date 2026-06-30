"""Generate playable packs from the question bank.

Queries the SQLite bank by theme (and optionally difficulty) and writes valid
``packs/`` files through ``packs_store.save_pack`` — so packs are normalised and
the game engine reads them unchanged. Supports QCM and Buzzer.

Run from the backend dir, e.g.:
    python -m scripts.bank.build_packs --all --mode qcm --limit 100 --min 20
    python -m scripts.bank.build_packs --theme geographie --mode buzzer
"""

from __future__ import annotations

import argparse
import json

from game import packs_store
from scripts.bank import bank_db
from scripts.bank.themes import THEMES

# Pretty names for pack titles / tags.
THEME_LABELS: dict[str, str] = {
    "animaux": "Animaux", "archeologie": "Archéologie", "arts": "Arts", "bd": "BD",
    "celebrites": "Célébrités", "cinema": "Cinéma", "culture": "Culture générale",
    "gastronomie": "Gastronomie", "geographie": "Géographie", "histoire": "Histoire",
    "informatique": "Informatique", "internet": "Internet", "litterature": "Littérature",
    "loisirs": "Loisirs", "monde": "Monde", "musique": "Musique", "nature": "Nature",
    "quotidien": "Quotidien", "sciences": "Sciences", "sports": "Sports",
    "television": "Télévision", "tourisme": "Tourisme",
    "jeux_video": "Jeux vidéo", "series": "Séries", "drapeaux": "Drapeaux",
    "rebus": "Rébus", "quatre_images": "4 images 1 mot",
}


def _qcm_item(row: dict) -> dict | None:
    choices = json.loads(row["choices_json"])
    if len(choices) != 4 or row["answer"] not in choices:
        return None
    points = bank_db.DIFFICULTY_POINTS.get(row.get("difficulty"), 1) * 1000
    return {
        "question": row["question"],
        "choices": choices,
        "correct": choices.index(row["answer"]),
        "time_limit": 20,
        "points": points,
        "bonus": False,
        "image": row.get("image"),
    }


def _buzzer_item(row: dict) -> dict:
    return {
        "question": row["question"],
        "answer": row["answer"],
        "points": bank_db.DIFFICULTY_POINTS.get(row.get("difficulty"), 1),
        "bonus": False,
        "image": row.get("image"),
    }


def build_one(conn, theme: str, mode: str, *, limit: int | None, difficulty: str | None) -> str | None:
    rows = bank_db.fetch(
        conn, theme=theme, difficulty=difficulty, require_choices=(mode == "qcm"), limit=limit
    )
    items: list[dict] = []
    for r in rows:
        if mode == "qcm":
            it = _qcm_item(dict(r))
            if it:
                items.append(it)
        else:
            items.append(_buzzer_item(dict(r)))
    if not items:
        return None

    label = THEME_LABELS.get(theme, theme.capitalize())
    mode_label = "QCM" if mode == "qcm" else "Buzzer"
    pack = {
        "name": f"{label} ({mode_label})",
        "description": f"Banque — {label}. {len(items)} questions ({mode_label}).",
        "tags": ["banque", label],
        "mode": mode,
        "items": items,
    }
    saved = packs_store.save_pack(pack)
    print(f"[pack] {saved['id']}  {pack['name']}  ({len(items)} questions)")
    return saved["id"]


def run() -> None:
    ap = argparse.ArgumentParser(description="Build packs from the question bank.")
    ap.add_argument("--theme", help="single theme (default: --all)")
    ap.add_argument("--all", action="store_true", help="build for every theme meeting --min")
    ap.add_argument("--mode", choices=["qcm", "buzzer"], default="qcm")
    ap.add_argument("--limit", type=int, default=None, help="max questions per pack")
    ap.add_argument("--min", type=int, default=10, help="skip themes with fewer than this many questions")
    ap.add_argument("--difficulty", choices=list(bank_db.DIFFICULTIES), default=None)
    args = ap.parse_args()

    conn = bank_db.connect()
    themes = [args.theme] if args.theme else (THEMES if args.all else [])
    if not themes:
        ap.error("specify --theme <name> or --all")

    counts = dict(bank_db.counts_by_theme(conn))
    built = 0
    for theme in themes:
        if counts.get(theme, 0) < args.min:
            continue
        if build_one(conn, theme, args.mode, limit=args.limit, difficulty=args.difficulty):
            built += 1
    print(f"[done] {built} pack(s) written to {packs_store._packs_dir()}")
    conn.close()


if __name__ == "__main__":
    run()
