# Bloc B (tranche 1) — Ingestion OpenTriviaQA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingérer les questions OpenTriviaQA (anglais, QCM) dans la banque SQLite, traduites en français et filtrées par qualité via Claude, avec un cache de traduction.

**Architecture:** Trois modules dans `backend/scripts/bank/` : `opentriviaqa.py` (fetch + parse → `QuestionDraft`), `translate.py` (un appel Claude par question via `httpx` brut → traduction + verdict de pertinence, avec cache JSON persistant), `ingest_opentriviaqa.py` (orchestration CLI : draft → traduit/filtre → thème → `bank_db.insert_question`). Ajout d'un thème `religion`.

**Tech Stack:** Python 3.12, stdlib `sqlite3`/`json`/`hashlib`/`re`, `httpx` (déjà présent), pytest. API Anthropic Messages.

## Global Constraints

- **Aucune commande git** (pas de commit/add/branche).
- **Aucun nouveau package** : appels Claude via `httpx` brut (pas de SDK anthropic).
- Français uniquement.
- Vocabulaire difficulté : `facile`, `moyen`, `difficile`, `inconnu` (du Bloc A).
- Modèle Claude par défaut `claude-sonnet-4-6`, surchargeable par env `TRANSLATE_MODEL`. ID exact, sans suffixe de date.
- API Messages : `POST https://api.anthropic.com/v1/messages` ; headers `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`. Clé via env `ANTHROPIC_API_KEY` (absente → `RuntimeError`).
- Cache de traduction : `data/translation_cache.json` (env `TRANSLATION_CACHE`), clé = SHA-1 du texte EN de la question. Ne jamais re-traduire une clé déjà en cache.
- Source insérée : `source="opentriviaqa"`.
- Lancer pytest et `python -m scripts.bank.*` depuis `backend/`.

---

### Task 1: Ajouter le thème `religion`

**Files:**
- Modify: `backend/scripts/bank/themes.py` (tuple `THEMES` ; dict `_KEYWORDS`)
- Modify: `backend/scripts/bank/build_packs.py` (dict `THEME_LABELS`)
- Test: `backend/tests/test_themes.py` (créer)

**Interfaces:**
- Produces: `"religion"` ∈ `themes.THEMES` ; `themes.classify(...)` peut renvoyer `"religion"` ; `build_packs.THEME_LABELS["religion"] == "Religion"`.

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_themes.py` :

```python
from scripts.bank import build_packs
from scripts.bank.themes import THEMES, classify


def test_religion_theme_registered():
    assert "religion" in THEMES
    assert build_packs.THEME_LABELS["religion"] == "Religion"


def test_classify_detects_religion():
    assert classify("Quel est le livre saint de l'islam ?", "Le Coran") == "religion"
    assert classify("Qui est le chef de l'Église catholique ?", "Le pape") == "religion"


def test_classify_still_detects_other_themes():
    assert classify("Quelle est la capitale de la France ?", "Paris") == "geographie"
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`): `python -m pytest tests/test_themes.py -v`
Expected: FAIL — `"religion"` absent de `THEMES` / `THEME_LABELS`.

- [ ] **Step 3: Add the theme**

Dans `backend/scripts/bank/themes.py`, ajouter `"religion"` à la fin du tuple `THEMES` (après `"quatre_images"`), et ajouter cette entrée dans `_KEYWORDS` :

```python
    "religion": ["religion", "dieu", "eglise", "bible", "coran", "priere", "saint",
                 "pape", "temple", "islam", "chretien", "juif", "boudhiste", "messe",
                 "prophete", "apotre", "cardinal"],
```

Dans `backend/scripts/bank/build_packs.py`, ajouter à `THEME_LABELS` :

```python
    "religion": "Religion",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_themes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: No commit.**

---

### Task 2: `opentriviaqa.py` — `QuestionDraft` + `parse_category`

**Files:**
- Create: `backend/scripts/bank/opentriviaqa.py`
- Test: `backend/tests/test_opentriviaqa.py` (créer)

**Interfaces:**
- Produces:
  - `@dataclass QuestionDraft(question: str, answer: str, choices: list[str], category: str, source_url: str)`
  - `parse_category(text: str, category: str, source_url: str = "") -> list[QuestionDraft]` — pure, sans réseau. Ne garde que les blocs à exactement 4 choix dont la bonne réponse (`^`) est l'un des choix.
  - `CATEGORIES: tuple[str, ...]`, `RAW_BASE: str`, `category_url(category: str) -> str`, `fetch_categories(categories: list[str]) -> dict[str, str]` (réseau via httpx).

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_opentriviaqa.py` :

```python
from scripts.bank import opentriviaqa
from scripts.bank.opentriviaqa import QuestionDraft

SAMPLE = """#Q What is the capital of Italy?
^ Rome
A Venice
B Rome
C Naples
D Milan

#Q What is the capital of Greece?
^ Athens
A Ankara
B Athens
C Sofia
D Thessaloniki
"""


def test_parse_returns_one_draft_per_valid_block():
    drafts = opentriviaqa.parse_category(SAMPLE, "geography", source_url="u")
    assert len(drafts) == 2
    assert drafts[0] == QuestionDraft(
        question="What is the capital of Italy?",
        answer="Rome",
        choices=["Venice", "Rome", "Naples", "Milan"],
        category="geography",
        source_url="u",
    )


def test_parse_skips_block_without_four_choices():
    text = "#Q Q1?\n^ A\nA A\nB B\nC C\n"  # only 3 choices
    assert opentriviaqa.parse_category(text, "general") == []


def test_parse_skips_block_when_answer_not_in_choices():
    text = "#Q Q1?\n^ Zzz\nA A\nB B\nC C\nD D\n"
    assert opentriviaqa.parse_category(text, "general") == []


def test_parse_joins_multiline_question():
    text = "#Q Line one\nstill the question\n^ A\nA A\nB B\nC C\nD D\n"
    drafts = opentriviaqa.parse_category(text, "general")
    assert len(drafts) == 1
    assert drafts[0].question == "Line one still the question"


def test_category_url():
    assert opentriviaqa.category_url("geography") == opentriviaqa.RAW_BASE + "/geography"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_opentriviaqa.py -v`
Expected: FAIL — module `opentriviaqa` n'existe pas.

- [ ] **Step 3: Write the implementation**

Créer `backend/scripts/bank/opentriviaqa.py` :

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_opentriviaqa.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: No commit.**

---

### Task 3: `translate.py` — traduction + filtre qualité + cache

**Files:**
- Create: `backend/scripts/bank/translate.py`
- Test: `backend/tests/test_translate.py` (créer)

**Interfaces:**
- Consumes: `opentriviaqa.QuestionDraft` (Task 2).
- Produces:
  - `@dataclass TranslatedQuestion(question: str, answer: str, choices: list[str], difficulty: str)`
  - `translate_question(draft: QuestionDraft) -> TranslatedQuestion | None` — `None` si Claude rejette (`garder=false`) ou si la cohérence échoue (≠4 choix, ou `bonne_reponse` hors choix). Utilise le cache ; n'appelle `_call_claude` que sur cache-miss.
  - `_call_claude(draft: QuestionDraft) -> dict` — appel httpx ; lève `RuntimeError` si `ANTHROPIC_API_KEY` absente. (Monkeypatché dans les tests.)

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_translate.py` :

```python
import pytest

from scripts.bank import translate
from scripts.bank.opentriviaqa import QuestionDraft
from scripts.bank.translate import TranslatedQuestion


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSLATION_CACHE", str(tmp_path / "cache.json"))


def _draft(q="What is the capital of Italy?"):
    return QuestionDraft(question=q, answer="Rome",
                         choices=["Venice", "Rome", "Naples", "Milan"], category="geography")


def test_translate_returns_translated_question(monkeypatch):
    monkeypatch.setattr(translate, "_call_claude", lambda d: {
        "garder": True, "question": "Quelle est la capitale de l'Italie ?",
        "choix": ["Venise", "Rome", "Naples", "Milan"], "bonne_reponse": "Rome",
        "difficulte": "facile",
    })
    tq = translate.translate_question(_draft())
    assert tq == TranslatedQuestion(
        question="Quelle est la capitale de l'Italie ?",
        answer="Rome", choices=["Venise", "Rome", "Naples", "Milan"], difficulty="facile")


def test_translate_rejects_when_garder_false(monkeypatch):
    monkeypatch.setattr(translate, "_call_claude", lambda d: {
        "garder": False, "question": "", "choix": [], "bonne_reponse": "", "difficulte": "facile"})
    assert translate.translate_question(_draft()) is None


def test_translate_rejects_when_answer_not_in_choices(monkeypatch):
    monkeypatch.setattr(translate, "_call_claude", lambda d: {
        "garder": True, "question": "Q", "choix": ["A", "B", "C", "D"],
        "bonne_reponse": "Z", "difficulte": "moyen"})
    assert translate.translate_question(_draft()) is None


def test_translate_rejects_when_not_four_choices(monkeypatch):
    monkeypatch.setattr(translate, "_call_claude", lambda d: {
        "garder": True, "question": "Q", "choix": ["A", "B", "C"],
        "bonne_reponse": "A", "difficulte": "moyen"})
    assert translate.translate_question(_draft()) is None


def test_cache_hit_does_not_recall_claude(monkeypatch):
    calls = {"n": 0}

    def fake(d):
        calls["n"] += 1
        return {"garder": True, "question": "Q", "choix": ["A", "B", "C", "D"],
                "bonne_reponse": "A", "difficulte": "moyen"}

    monkeypatch.setattr(translate, "_call_claude", fake)
    translate.translate_question(_draft())
    translate.translate_question(_draft())  # same EN question -> cache hit
    assert calls["n"] == 1


def test_call_claude_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        translate._call_claude(_draft())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_translate.py -v`
Expected: FAIL — module `translate` n'existe pas.

- [ ] **Step 3: Write the implementation**

Créer `backend/scripts/bank/translate.py` :

```python
"""Translate + quality-filter an English QuestionDraft into French via Claude.

One Claude call per question (raw httpx on the Anthropic Messages API — no SDK),
with a persistent JSON cache keyed by the SHA-1 of the English question so a
string is never translated twice. Claude also judges cultural relevance for a
French audience: garder=false drops US-centric / untranslatable / poor questions.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from scripts.bank.opentriviaqa import QuestionDraft

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM = (
    "Tu adaptes des questions de quiz anglaises pour une soirée quiz francophone. "
    "Traduis fidèlement en français la question, les quatre choix et la bonne réponse. "
    "Mets \"garder\": false si la question est trop spécifiquement américaine/anglo-saxonne, "
    "intraduisible, ambiguë, ou de mauvaise qualité pour un public français. "
    "\"bonne_reponse\" doit être exactement l'un des quatre choix traduits. "
    "Estime la difficulté : facile, moyen ou difficile."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "garder": {"type": "boolean"},
        "question": {"type": "string"},
        "choix": {"type": "array", "items": {"type": "string"}},
        "bonne_reponse": {"type": "string"},
        "difficulte": {"type": "string", "enum": ["facile", "moyen", "difficile"]},
    },
    "required": ["garder", "question", "choix", "bonne_reponse", "difficulte"],
    "additionalProperties": False,
}


@dataclass
class TranslatedQuestion:
    question: str
    answer: str
    choices: list[str]
    difficulty: str


def _cache_path() -> Path:
    return Path(os.environ.get("TRANSLATION_CACHE", "data/translation_cache.json"))


def _load_cache() -> dict:
    p = _cache_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _call_claude(draft: QuestionDraft) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY manquante : exporte-la avant de traduire.")
    model = os.environ.get("TRANSLATE_MODEL", DEFAULT_MODEL)
    user = (
        f"Question : {draft.question}\n"
        f"Choix : {' | '.join(draft.choices)}\n"
        f"Bonne réponse : {draft.answer}"
    )
    body = {
        "model": model,
        "max_tokens": 1024,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": _SCHEMA}},
    }
    resp = httpx.post(
        API_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    text = next(b["text"] for b in data["content"] if b["type"] == "text")
    return json.loads(text)


def translate_question(draft: QuestionDraft) -> TranslatedQuestion | None:
    cache = _load_cache()
    key = hashlib.sha1(draft.question.encode("utf-8")).hexdigest()
    if key in cache:
        result = cache[key]
    else:
        result = _call_claude(draft)
        cache[key] = result
        _save_cache(cache)
    if not result.get("garder"):
        return None
    choix = [str(c).strip() for c in (result.get("choix") or [])]
    bonne = str(result.get("bonne_reponse") or "").strip()
    if len(choix) != 4 or bonne not in choix:
        return None
    diff = result.get("difficulte")
    if diff not in ("facile", "moyen", "difficile"):
        diff = "inconnu"
    return TranslatedQuestion(
        question=str(result.get("question") or "").strip(),
        answer=bonne, choices=choix, difficulty=diff,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_translate.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: No commit.**

---

### Task 4: `ingest_opentriviaqa.py` — mapping thème + orchestration

**Files:**
- Create: `backend/scripts/bank/ingest_opentriviaqa.py`
- Test: `backend/tests/test_ingest_opentriviaqa.py` (créer)

**Interfaces:**
- Consumes: `opentriviaqa.parse_category`/`fetch_categories`/`CATEGORIES`/`QuestionDraft` (Task 2), `translate.translate_question`/`TranslatedQuestion` (Task 3), `bank_db.connect`/`insert_question` (Bloc A), `themes.classify`/`THEMES`, le thème `religion` (Task 1).
- Produces:
  - `CATEGORY_THEME: dict[str, str]`
  - `theme_for(category: str, question_fr: str, answer_fr: str, choices_fr: list[str]) -> str` — catégorie mappée si présente dans `THEMES`, sinon `classify(...)`.
  - `ingest(conn, drafts: list[QuestionDraft], *, limit: int | None = None) -> dict` → `{"inserted", "rejected", "duplicates"}`. Appelle `translate.translate_question` par draft.
  - `run() -> None` — CLI (`--limit`, `--category`).

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_ingest_opentriviaqa.py` :

```python
import pytest

from scripts.bank import bank_db, ingest_opentriviaqa, translate
from scripts.bank.opentriviaqa import QuestionDraft
from scripts.bank.translate import TranslatedQuestion


@pytest.fixture
def tmp_bank(tmp_path, monkeypatch):
    monkeypatch.setenv("BANK_DB", str(tmp_path / "bank.db"))
    return tmp_path


def test_theme_for_uses_category_map():
    assert ingest_opentriviaqa.theme_for("video-games", "q", "a", ["a"]) == "jeux_video"
    assert ingest_opentriviaqa.theme_for("religion-faith", "q", "a", ["a"]) == "religion"


def test_theme_for_falls_back_to_classify():
    # "general" is not mapped -> classify on the FR text
    assert ingest_opentriviaqa.theme_for(
        "general", "Quelle est la capitale de la France ?", "Paris", []) == "geographie"


def test_ingest_inserts_translated_and_counts_rejects(tmp_bank, monkeypatch):
    drafts = [
        QuestionDraft("Capital of Italy?", "Rome", ["Venice", "Rome", "Naples", "Milan"], "geography"),
        QuestionDraft("US-only trivia?", "X", ["X", "Y", "Z", "W"], "general"),
    ]

    def fake_translate(d):
        if d.question == "Capital of Italy?":
            return TranslatedQuestion("Capitale de l'Italie ?", "Rome",
                                      ["Venise", "Rome", "Naples", "Milan"], "facile")
        return None  # rejected by Claude

    monkeypatch.setattr(translate, "translate_question", fake_translate)
    conn = bank_db.connect()
    counts = ingest_opentriviaqa.ingest(conn, drafts)
    assert counts == {"inserted": 1, "rejected": 1, "duplicates": 0}
    rows = list(conn.execute("SELECT theme, difficulty, source FROM questions"))
    assert len(rows) == 1
    assert rows[0]["theme"] == "geographie"
    assert rows[0]["difficulty"] == "facile"
    assert rows[0]["source"] == "opentriviaqa"
    conn.close()


def test_ingest_respects_limit(tmp_bank, monkeypatch):
    drafts = [
        QuestionDraft(f"Q{i}?", "Rome", ["Venice", "Rome", "Naples", "Milan"], "geography")
        for i in range(5)
    ]
    monkeypatch.setattr(translate, "translate_question", lambda d: TranslatedQuestion(
        d.question, "Rome", ["Venise", "Rome", "Naples", "Milan"], "moyen"))
    conn = bank_db.connect()
    counts = ingest_opentriviaqa.ingest(conn, drafts, limit=2)
    assert counts["inserted"] == 2
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest_opentriviaqa.py -v`
Expected: FAIL — module `ingest_opentriviaqa` n'existe pas.

- [ ] **Step 3: Write the implementation**

Créer `backend/scripts/bank/ingest_opentriviaqa.py` :

```python
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
    "religion-faith": "religion",
    "hobbies": "loisirs",
    "humanities": "arts",
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ingest_opentriviaqa.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Full suite**

Run (depuis `backend/`): `python -m pytest -v`
Expected: tout vert (aucune régression).

- [ ] **Step 6: No commit.**

---

## Vérification end-to-end (manuelle, nécessite une clé API)

Depuis `backend/`, avec `ANTHROPIC_API_KEY` exporté (PowerShell : `$env:ANTHROPIC_API_KEY="..."`):

```
python -m scripts.bank.ingest_opentriviaqa --category geography --limit 100
node scripts/bank/review.js
```
Ouvrir `backend/scripts/bank/review.html`, filtrer/relire les questions `source=opentriviaqa` : traductions FR lisibles, pertinentes pour un public français, bien classées par thème, difficulté cohérente. Vérifier que `data/translation_cache.json` a été créé et qu'une 2ᵉ exécution ne re-traduit pas (rapide, pas d'appels). Si la qualité convient → lever `--limit` et planifier la tranche suivante (Hugging Face).

## Notes d'exécution

- Pas de git. Lancer pytest / `python -m scripts.bank.*` depuis `backend/`.
- Les tests ne font **aucun** appel réseau ni Claude (parse pur ; `_call_claude` et `translate_question` monkeypatchés ; `fetch_categories` non testé).
