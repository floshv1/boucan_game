"""Fetch + parse the OpenTriviaQA corpus (uberspot/OpenTriviaQA).

Each category file is plain text; question blocks are separated by blank lines:

    #Q <question text (may span lines until ^)>
    ^ <correct answer>
    A <choice>
    B <choice>
    C <choice>
    D <choice>

Only blocks with exactly 4 choices whose correct answer is among them are kept
(needed for QCM; buzzer ignores the choices). English — translated later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

RAW_BASE = "https://raw.githubusercontent.com/uberspot/OpenTriviaQA/master/categories"

CATEGORIES: tuple[str, ...] = (
    "animals", "brain-teasers", "celebrities", "entertainment", "for-kids",
    "general", "geography", "history", "hobbies", "humanities", "literature",
    "movies", "music", "people", "religion-faith", "science-technology",
    "sports", "television", "video-games", "world",
)


@dataclass
class QuestionDraft:
    question: str
    answer: str
    choices: list[str]
    category: str
    source_url: str = ""


def parse_category(text: str, category: str, source_url: str = "") -> list[QuestionDraft]:
    drafts: list[QuestionDraft] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        q_lines: list[str] = []
        answer: str | None = None
        choices: list[str] = []
        for line in block.splitlines():
            if line.startswith("#Q "):
                q_lines.append(line[3:].strip())
            elif line.startswith("^ "):
                answer = line[2:].strip()
            # Limite du format texte : une ligne de continuation de question commençant
            # par "A "/"B "/"C "/"D " sera prise pour un choix ; le bloc, mal formé, sera
            # alors écarté par le contrôle len(choices)==4 plus bas.
            elif len(line) >= 2 and line[0] in "ABCD" and line[1] == " ":
                choices.append(line[2:].strip())
            elif q_lines and answer is None:
                # continuation of a multi-line question (before the ^ line)
                q_lines.append(line.strip())
        question = " ".join(p for p in q_lines if p).strip()
        if not question or not answer or len(choices) != 4 or answer not in choices:
            continue
        drafts.append(
            QuestionDraft(
                question=question, answer=answer, choices=choices,
                category=category, source_url=source_url,
            )
        )
    return drafts


def category_url(category: str) -> str:
    return f"{RAW_BASE}/{category}"


def fetch_categories(categories: list[str]) -> dict[str, str]:
    """Download raw category texts via httpx. Network — not unit-tested."""
    out: dict[str, str] = {}
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for cat in categories:
            out[cat] = client.get(category_url(cat)).text
    return out
