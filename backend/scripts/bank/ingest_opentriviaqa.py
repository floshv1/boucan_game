"""Ingest OpenTriviaQA into the question bank (translated + quality-filtered).

Run from the backend dir:
    python -m scripts.bank.ingest_opentriviaqa --limit 100      # essai
    python -m scripts.bank.ingest_opentriviaqa                  # tout
    python -m scripts.bank.ingest_opentriviaqa --category geography
Requires ANTHROPIC_API_KEY (translation). Difficulty/points come from Bloc A.
"""

from __future__ import annotations

import argparse

from scripts.bank import bank_db, opentriviaqa, translate
from scripts.bank.opentriviaqa import QuestionDraft
from scripts.bank.themes import THEMES, classify

# OpenTriviaQA category -> bank theme. Unmapped categories fall back to classify().
CATEGORY_THEME: dict[str, str] = {
    "animals": "animaux",
    "geography": "geographie",
    "history": "histoire",
    "literature": "litterature",
    "movies": "cinema",
    "music": "musique",
    "science-technology": "sciences",
    "sports": "sports",
    "television": "television",
    "video-games": "jeux_video",
    "world": "monde",
    "people": "celebrites",
    "celebrities": "celebrites",
    "hobbies": "gastronomie",
}


def theme_for(category: str, question_fr: str, answer_fr: str, choices_fr: list[str]) -> str:
    mapped = CATEGORY_THEME.get(category)
    if mapped in THEMES:
        return mapped
    return classify(question_fr, answer_fr, choices_fr)


def ingest(conn, drafts: list[QuestionDraft], *, limit: int | None = None) -> dict:
    inserted = rejected = duplicates = 0
    for i, draft in enumerate(drafts):
        if limit is not None and i >= limit:
            break
        tq = translate.translate_question(draft)
        if tq is None:
            rejected += 1
            continue
        theme = theme_for(draft.category, tq.question, tq.answer, tq.choices)
        ok = bank_db.insert_question(
            conn,
            question=tq.question,
            answer=tq.answer,
            choices=tq.choices,
            theme=theme,
            difficulty=tq.difficulty,
            source="opentriviaqa",
            source_url=draft.source_url or opentriviaqa.category_url(draft.category),
        )
        if ok:
            inserted += 1
        else:
            duplicates += 1
        conn.commit()
    return {"inserted": inserted, "rejected": rejected, "duplicates": duplicates}


def run() -> None:
    ap = argparse.ArgumentParser(description="Ingest OpenTriviaQA into the bank.")
    ap.add_argument("--limit", type=int, default=None, help="max questions traitées")
    ap.add_argument("--category", default=None, help="une seule catégorie OpenTriviaQA")
    args = ap.parse_args()

    categories = [args.category] if args.category else list(opentriviaqa.CATEGORIES)
    texts = opentriviaqa.fetch_categories(categories)
    drafts: list[QuestionDraft] = []
    for cat, text in texts.items():
        drafts.extend(opentriviaqa.parse_category(text, cat, source_url=opentriviaqa.category_url(cat)))

    conn = bank_db.connect()
    counts = ingest(conn, drafts, limit=args.limit)
    print(
        f"[opentriviaqa] inserted={counts['inserted']} "
        f"rejected={counts['rejected']} duplicates={counts['duplicates']} "
        f"(drafts parsed={len(drafts)})"
    )
    print(f"[bank] total={bank_db.total(conn)}")
    conn.close()


if __name__ == "__main__":
    run()
