"""Import questions from the OpenQuizzDB REST API into the bank.

OpenQuizzDB (https://www.openquizzdb.org) is French-native with 22 broad themes
and a difficulty level, CC BY-SA 4.0. Constraints: a free key is requested by
e-mail, you get ~200 calls, and **each call returns a single question**. So this
harvests slowly and stops cleanly on quota (response_code 5).

Get a key at https://www.openquizzdb.org/ then:
    OPENQUIZZDB_KEY=xxxx python -m scripts.bank.import_openquizzdb --per-theme 8

Without a key it prints how to get one and exits.
"""

from __future__ import annotations

import argparse
import os
import time

import httpx

from scripts.bank import bank_db

API = "https://api.openquizzdb.org/"
SOURCE = "openquizzdb"
SOURCE_URL = "https://www.openquizzdb.org/"

# OpenQuizzDB categories == our broad themes (themes.THEMES mirrors this list).
CATEGORIES = [
    "animaux", "archeologie", "arts", "bd", "celebrites", "cinema", "culture",
    "gastronomie", "geographie", "histoire", "informatique", "internet",
    "litterature", "loisirs", "monde", "musique", "nature", "quotidien",
    "sciences", "sports", "television", "tourisme",
]
# diff param -> our difficulty label
_DIFF = {1: "debutant", 2: "intermediaire", 3: "expert"}


def _fetch_one(client: httpx.Client, key: str, categ: str, diff: int) -> tuple[int, dict | None]:
    r = client.get(API, params={"key": key, "categ": categ, "diff": diff, "anec": 1, "wiki": 1})
    data = r.json()
    code = int(data.get("response_code", -1))
    results = data.get("results") or []
    return code, (results[0] if results else None)


def run() -> None:
    ap = argparse.ArgumentParser(description="Harvest OpenQuizzDB into the bank (quota-limited).")
    ap.add_argument("--per-theme", type=int, default=8, help="calls per (theme × difficulty)")
    ap.add_argument("--sleep", type=float, default=0.4, help="seconds between calls (be polite)")
    args = ap.parse_args()

    key = os.environ.get("OPENQUIZZDB_KEY")
    if not key:
        print("No OPENQUIZZDB_KEY set. Request a free key at https://www.openquizzdb.org/ "
              "then re-run:  OPENQUIZZDB_KEY=xxxx python -m scripts.bank.import_openquizzdb")
        return

    conn = bank_db.connect()
    inserted = dups = calls = 0
    with httpx.Client(timeout=30.0) as client:
        for categ in CATEGORIES:
            for diff in (1, 2, 3):
                for _ in range(args.per_theme):
                    code, item = _fetch_one(client, key, categ, diff)
                    calls += 1
                    if code == 5:
                        print(f"[openquizzdb] quota reached after {calls} calls.")
                        conn.commit()
                        _summary(conn, inserted, dups, calls)
                        return
                    if code != 0 or not item:
                        if code not in (0,):  # 1=bad param, 2=bad key, etc.
                            print(f"[openquizzdb] stop: response_code={code}")
                            conn.commit()
                            _summary(conn, inserted, dups, calls)
                            return
                        continue
                    answer = str(item.get("reponse_correcte") or "").strip()
                    others = [str(c).strip() for c in (item.get("autres_choix") or [])]
                    choices = [answer, *others] if answer and len(others) == 3 else []
                    ok = bank_db.insert_question(
                        conn,
                        question=str(item.get("question") or "").strip(),
                        answer=answer,
                        choices=choices,
                        theme=categ,
                        difficulty=_DIFF.get(diff, "inconnu"),
                        source=SOURCE,
                        source_url=item.get("wikipedia") or SOURCE_URL,
                        anecdote=(str(item.get("anecdote")).strip() if item.get("anecdote") else None),
                    )
                    inserted += ok
                    dups += (not ok)
                    time.sleep(args.sleep)
                conn.commit()
    _summary(conn, inserted, dups, calls)


def _summary(conn, inserted: int, dups: int, calls: int) -> None:
    print(f"[openquizzdb] calls={calls} inserted={inserted} duplicates={dups}")
    print(f"[bank] total={bank_db.total(conn)}")
    conn.close()


if __name__ == "__main__":
    run()
