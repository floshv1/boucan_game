"""Load AI-generated French questions into the bank.

This is the "volume" source: JsonQuizz + OpenQuizzDB provide a vetted base, and
hand-curated AI batches top each broad theme up toward 100+. Each file in
``scripts/bank/aigen/*.json`` looks like:

    {
      "theme": "histoire",            # one of themes.THEMES
      "difficulty": "intermediaire",  # debutant | intermediaire | expert
      "questions": [
        {"question": "...", "choices": ["A","B","C","D"], "answer": "B", "anecdote": "..."}
      ]
    }

``answer`` must be one of ``choices`` (4 choices). Dedup against the rest of the
bank is automatic (qhash). Run:  ``python -m scripts.bank.import_aigen``
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.bank import bank_db
from scripts.bank.themes import THEMES

AIGEN_DIR = Path(__file__).parent / "aigen"
SOURCE = "aigen"


def _load_file(conn, path: Path) -> tuple[int, int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    theme = str(data.get("theme") or "").strip()
    difficulty = str(data.get("difficulty") or "inconnu").strip()
    if theme not in THEMES:
        print(f"[aigen] {path.name}: unknown theme {theme!r} — skipped")
        return 0, 0, 0
    inserted = dups = bad = 0
    for q in data.get("questions") or []:
        question = str(q.get("question") or "").strip()
        answer = str(q.get("answer") or "").strip()
        choices = [str(c).strip() for c in (q.get("choices") or []) if str(c).strip()]
        if len(choices) != 4 or answer not in choices:
            bad += 1
            continue
        ok = bank_db.insert_question(
            conn,
            question=question,
            answer=answer,
            choices=choices,
            theme=theme,
            difficulty=difficulty,
            source=SOURCE,
            source_url=str(path.relative_to(AIGEN_DIR.parent)),
            anecdote=(str(q.get("anecdote")).strip() if q.get("anecdote") else None),
        )
        inserted += ok
        dups += (not ok)
    print(f"[aigen] {path.name}: inserted={inserted} duplicates={dups} invalid={bad}")
    return inserted, dups, bad


def run() -> None:
    conn = bank_db.connect()
    AIGEN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(AIGEN_DIR.glob("*.json"))
    if not files:
        print(f"[aigen] no files in {AIGEN_DIR} — nothing to import.")
        return
    tot_i = tot_d = tot_b = 0
    for path in files:
        i, d, b = _load_file(conn, path)
        tot_i += i
        tot_d += d
        tot_b += b
        conn.commit()
    print(f"[aigen] TOTAL inserted={tot_i} duplicates={tot_d} invalid={tot_b}")
    print(f"[bank] total={bank_db.total(conn)}")
    conn.close()


if __name__ == "__main__":
    run()
