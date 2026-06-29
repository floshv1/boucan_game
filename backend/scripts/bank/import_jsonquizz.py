"""Import the JsonQuizz French corpus into the question bank.

Source: https://github.com/SimonLeclere/JsonQuizz (free to reuse, ~1140 FR QCM
across débutant/intermédiaire/expert). Each item is
``{question, propositions[4], réponse, anecdote}``. We map propositions→choices,
réponse→answer, difficulty from the filename, and classify a broad theme.

Run from the backend dir:  ``python -m scripts.bank.import_jsonquizz``
"""

from __future__ import annotations

import httpx

from scripts.bank import bank_db
from scripts.bank.themes import classify

_BASE = "https://raw.githubusercontent.com/SimonLeclere/JsonQuizz/master/fr"
_FILES = {
    "debutant": f"{_BASE}/quizz-d%C3%A9butant.json",
    "intermediaire": f"{_BASE}/quizz-interm%C3%A9diaire.json",
    "expert": f"{_BASE}/quizz-expert.json",
}
SOURCE = "jsonquizz"
SOURCE_URL = "https://github.com/SimonLeclere/JsonQuizz"


def run() -> None:
    conn = bank_db.connect()
    inserted = dups = skipped = 0
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for difficulty, url in _FILES.items():
            data = client.get(url).json()
            for item in data:
                question = str(item.get("question") or "").strip()
                answer = str(item.get("réponse") or "").strip()
                choices = [str(c).strip() for c in (item.get("propositions") or []) if str(c).strip()]
                anecdote = str(item.get("anecdote") or "").strip() or None
                # Only keep choices if the answer is actually among them (so QCM is well-formed).
                if answer not in choices:
                    choices = []
                if not question or not answer:
                    skipped += 1
                    continue
                ok = bank_db.insert_question(
                    conn,
                    question=question,
                    answer=answer,
                    choices=choices,
                    theme=classify(question, answer, choices),
                    difficulty=difficulty,
                    source=SOURCE,
                    source_url=SOURCE_URL,
                    anecdote=anecdote,
                )
                if ok:
                    inserted += 1
                else:
                    dups += 1
            conn.commit()
    print(f"[jsonquizz] inserted={inserted} duplicates={dups} skipped={skipped}")
    print(f"[bank] total={bank_db.total(conn)}")
    conn.close()


if __name__ == "__main__":
    run()
