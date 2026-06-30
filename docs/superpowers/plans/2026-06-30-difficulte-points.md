# Difficulté standardisée + points liés — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardiser la difficulté des questions en `facile/moyen/difficile`, lier les points par défaut à la difficulté (1/2/3), et confirmer que toute question à 4 choix sert aux modes buzzer et QCM.

**Architecture:** La difficulté vit dans la banque SQLite (`bank_db.py`). Une fonction de normalisation mappe l'ancien vocabulaire (`debutant/intermediaire/expert`) vers le nouveau, à l'import et via une migration DB unique. Le mapping difficulté→points s'applique à la génération des packs (`build_packs.py`), pas au runtime du jeu. L'éditeur frontend garde les points modifiables (valeur par défaut).

**Tech Stack:** Python 3.12 (stdlib `sqlite3`), pytest. Aucune nouvelle dépendance.

## Global Constraints

- **Aucune commande git** (pas de commit/add) — demandé explicitement par l'utilisateur.
- Français uniquement.
- Vocabulaire de difficulté autorisé : `facile`, `moyen`, `difficile`, `inconnu` (exactement).
- Mapping points par défaut : `facile=1`, `moyen=2`, `difficile=3`, `inconnu=1`.
- QCM : points de base = `difficulté × 1000` (1000/2000/3000) ; Buzzer : points = `difficulté` (1/2/3).
- Backend lancé depuis `backend/` ; tests via `pytest` depuis `backend/`.

---

### Task 1: Vocabulaire de difficulté + mapping points dans `bank_db.py`

**Files:**
- Modify: `backend/scripts/bank/bank_db.py` (constante `DIFFICULTIES` ligne 23 ; appel dans `insert_question` ligne 108)
- Test: `backend/tests/test_bank_db.py` (créer)

**Interfaces:**
- Produces:
  - `bank_db.DIFFICULTIES: tuple[str, ...]` = `("facile", "moyen", "difficile", "inconnu")`
  - `bank_db.normalize_difficulty(value: str) -> str`
  - `bank_db.DIFFICULTY_POINTS: dict[str, int]` = `{"facile": 1, "moyen": 2, "difficile": 3, "inconnu": 1}`

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_bank_db.py` :

```python
from scripts.bank import bank_db


def test_difficulties_use_new_vocabulary():
    assert bank_db.DIFFICULTIES == ("facile", "moyen", "difficile", "inconnu")


def test_normalize_difficulty_maps_legacy_values():
    assert bank_db.normalize_difficulty("debutant") == "facile"
    assert bank_db.normalize_difficulty("intermediaire") == "moyen"
    assert bank_db.normalize_difficulty("expert") == "difficile"


def test_normalize_difficulty_passes_through_new_values():
    assert bank_db.normalize_difficulty("facile") == "facile"
    assert bank_db.normalize_difficulty("moyen") == "moyen"
    assert bank_db.normalize_difficulty("difficile") == "difficile"


def test_normalize_difficulty_unknown_falls_back():
    assert bank_db.normalize_difficulty("") == "inconnu"
    assert bank_db.normalize_difficulty("n'importe quoi") == "inconnu"
    assert bank_db.normalize_difficulty("EXPERT") == "difficile"  # case-insensitive


def test_difficulty_points_mapping():
    assert bank_db.DIFFICULTY_POINTS == {"facile": 1, "moyen": 2, "difficile": 3, "inconnu": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`): `pytest tests/test_bank_db.py -v`
Expected: FAIL — `DIFFICULTIES` vaut encore l'ancien tuple ; `normalize_difficulty` / `DIFFICULTY_POINTS` n'existent pas (`AttributeError`).

- [ ] **Step 3: Write minimal implementation**

Dans `backend/scripts/bank/bank_db.py`, remplacer la ligne 23 :

```python
DIFFICULTIES = ("facile", "moyen", "difficile", "inconnu")

_LEGACY_DIFFICULTY = {"debutant": "facile", "intermediaire": "moyen", "expert": "difficile"}

# Points par défaut selon la difficulté (valeur de base ; QCM la multiplie par 1000).
DIFFICULTY_POINTS = {"facile": 1, "moyen": 2, "difficile": 3, "inconnu": 1}


def normalize_difficulty(value: str) -> str:
    """Map legacy difficulty labels to the new vocabulary; unknown -> 'inconnu'."""
    v = (value or "").strip().lower()
    v = _LEGACY_DIFFICULTY.get(v, v)
    return v if v in DIFFICULTIES else "inconnu"
```

Puis dans `insert_question`, remplacer la ligne 108 :

```python
    difficulty = difficulty if difficulty in DIFFICULTIES else "inconnu"
```

par :

```python
    difficulty = normalize_difficulty(difficulty)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bank_db.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: No commit** (git désactivé sur ce projet pour cette tâche).

---

### Task 2: Migration DB des anciennes valeurs de difficulté

**Files:**
- Modify: `backend/scripts/bank/bank_db.py` (fonction `_migrate` lignes 59-64)
- Test: `backend/tests/test_bank_db.py` (ajouter)

**Interfaces:**
- Consumes: `bank_db._LEGACY_DIFFICULTY` (Task 1), `bank_db.connect()`, `bank_db.db_path()`
- Produces: `_migrate(conn)` convertit en place toute ligne avec une difficulté héritée.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_bank_db.py` :

```python
import pytest


@pytest.fixture
def tmp_bank(tmp_path, monkeypatch):
    monkeypatch.setenv("BANK_DB", str(tmp_path / "bank.db"))
    return tmp_path


def test_migrate_converts_legacy_difficulty_rows(tmp_bank):
    conn = bank_db.connect()
    # Insert legacy values directly (bypass insert_question normalisation).
    for i, legacy in enumerate(["debutant", "intermediaire", "expert"]):
        conn.execute(
            "INSERT INTO questions (question, answer, choices_json, theme, difficulty, source, qhash, created_at) "
            "VALUES (?, 'a', '[]', 'culture', ?, 'test', ?, '2026-01-01')",
            (f"q{i}", legacy, f"hash{i}"),
        )
    conn.commit()

    bank_db._migrate(conn)

    rows = {r["question"]: r["difficulty"] for r in conn.execute("SELECT question, difficulty FROM questions")}
    assert rows == {"q0": "facile", "q1": "moyen", "q2": "difficile"}

    # Idempotent: a second run changes nothing.
    bank_db._migrate(conn)
    rows2 = {r["question"]: r["difficulty"] for r in conn.execute("SELECT question, difficulty FROM questions")}
    assert rows2 == rows
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bank_db.py::test_migrate_converts_legacy_difficulty_rows -v`
Expected: FAIL — les difficultés restent `debutant/intermediaire/expert`.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/scripts/bank/bank_db.py`, étendre `_migrate` :

```python
def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the first DBs were created, and convert
    legacy difficulty labels to the new vocabulary (facile/moyen/difficile)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(questions)")}
    if "image" not in cols:
        conn.execute("ALTER TABLE questions ADD COLUMN image TEXT")
        conn.commit()
    for legacy, new in _LEGACY_DIFFICULTY.items():
        conn.execute("UPDATE questions SET difficulty = ? WHERE difficulty = ?", (new, legacy))
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bank_db.py -v`
Expected: PASS (tous les tests bank_db).

- [ ] **Step 5: No commit.**

---

### Task 3: Points liés à la difficulté dans `build_packs.py`

**Files:**
- Modify: `backend/scripts/bank/build_packs.py` (`_qcm_item` lignes 35-47 ; `_buzzer_item` lignes 50-57)
- Test: `backend/tests/test_build_packs.py` (créer)

**Interfaces:**
- Consumes: `bank_db.DIFFICULTY_POINTS` (Task 1)
- Produces: `_qcm_item(row)` et `_buzzer_item(row)` dérivent `points` de `row["difficulty"]`.

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_build_packs.py` :

```python
from scripts.bank import build_packs


def _row(difficulty):
    return {
        "question": "Capitale de la France ?",
        "answer": "Paris",
        "choices_json": '["Paris", "Lyon", "Nice", "Lille"]',
        "difficulty": difficulty,
        "image": None,
    }


def test_buzzer_points_follow_difficulty():
    assert build_packs._buzzer_item(_row("facile"))["points"] == 1
    assert build_packs._buzzer_item(_row("moyen"))["points"] == 2
    assert build_packs._buzzer_item(_row("difficile"))["points"] == 3
    assert build_packs._buzzer_item(_row("inconnu"))["points"] == 1


def test_qcm_points_follow_difficulty():
    assert build_packs._qcm_item(_row("facile"))["points"] == 1000
    assert build_packs._qcm_item(_row("moyen"))["points"] == 2000
    assert build_packs._qcm_item(_row("difficile"))["points"] == 3000


def test_qcm_item_keeps_correct_index_and_choices():
    item = build_packs._qcm_item(_row("moyen"))
    assert item["choices"] == ["Paris", "Lyon", "Nice", "Lille"]
    assert item["correct"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_packs.py -v`
Expected: FAIL — points valent encore `1000` (QCM) et `1` (buzzer) en dur.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/scripts/bank/build_packs.py`, modifier `_qcm_item` :

```python
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
```

Et `_buzzer_item` :

```python
def _buzzer_item(row: dict) -> dict:
    return {
        "question": row["question"],
        "answer": row["answer"],
        "points": bank_db.DIFFICULTY_POINTS.get(row.get("difficulty"), 1),
        "bonus": False,
        "image": row.get("image"),
    }
```

(`bank_db` est déjà importé en haut du fichier : `from scripts.bank import bank_db`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_packs.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: No commit.**

---

### Task 4: Mettre les fichiers `aigen/*.json` au nouveau vocabulaire

**Files:**
- Modify: `backend/scripts/bank/aigen/*.json` (16 fichiers — champ `"difficulty"`)
- Test: `backend/tests/test_bank_db.py` (ajouter un test de garde)

**Interfaces:**
- Consumes: `bank_db.DIFFICULTIES` (Task 1)

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_bank_db.py` :

```python
import json
from pathlib import Path


def test_aigen_files_use_new_difficulty_vocabulary():
    aigen = Path(__file__).resolve().parent.parent / "scripts" / "bank" / "aigen"
    legacy = {"debutant", "intermediaire", "expert"}
    offenders = []
    for path in sorted(aigen.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if str(data.get("difficulty", "")).strip().lower() in legacy:
            offenders.append(path.name)
    assert offenders == [], f"fichiers avec ancien vocabulaire: {offenders}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bank_db.py::test_aigen_files_use_new_difficulty_vocabulary -v`
Expected: FAIL — plusieurs fichiers contiennent encore `intermediaire` / `debutant` / `expert`.

- [ ] **Step 3: Rewrite the difficulty field in each file**

Exécuter (depuis `backend/`) ce script de réécriture in-place (préserve le contenu, ne touche qu'au champ `difficulty`) :

```python
import json
from pathlib import Path

LEGACY = {"debutant": "facile", "intermediaire": "moyen", "expert": "difficile"}
aigen = Path("scripts/bank/aigen")
for path in sorted(aigen.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    cur = str(data.get("difficulty", "")).strip().lower()
    if cur in LEGACY:
        data["difficulty"] = LEGACY[cur]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: {cur} -> {data['difficulty']}")
```

Enregistrer ce script dans le dossier scratchpad (hors repo), l'exécuter avec `python <chemin>`, puis ne rien laisser dans le repo. Sortie attendue : une ligne `xxx_01.json: intermediaire -> moyen` par fichier modifié.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bank_db.py::test_aigen_files_use_new_difficulty_vocabulary -v`
Expected: PASS.

- [ ] **Step 5: No commit.**

---

### Task 5: Vérifier la disponibilité dual buzzer/QCM

**Files:**
- Test: `backend/tests/test_build_packs.py` (ajouter)

**Interfaces:**
- Consumes: `build_packs._qcm_item`, `build_packs._buzzer_item` (Task 3)

- [ ] **Step 1: Write the failing test (puis vérifier qu'il passe — c'est une garde de comportement existant)**

Ajouter à `backend/tests/test_build_packs.py` :

```python
def test_four_choice_question_serves_both_modes():
    row = {
        "question": "Capitale de l'Italie ?",
        "answer": "Rome",
        "choices_json": '["Rome", "Milan", "Naples", "Turin"]',
        "difficulty": "moyen",
        "image": None,
    }
    qcm = build_packs._qcm_item(row)
    buzzer = build_packs._buzzer_item(row)

    assert qcm is not None and len(qcm["choices"]) == 4
    assert qcm["choices"][qcm["correct"]] == "Rome"
    assert buzzer["answer"] == "Rome"
    # Même difficulté -> points cohérents entre modes (×1000 pour QCM).
    assert qcm["points"] == buzzer["points"] * 1000
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_build_packs.py::test_four_choice_question_serves_both_modes -v`
Expected: PASS (le comportement dual est déjà en place ; ce test le verrouille).

- [ ] **Step 3: Full suite + end-to-end manuel**

Run (depuis `backend/`):
```
pytest
python -m scripts.bank.import_aigen
python -m scripts.bank.build_packs --all --mode qcm
python -m scripts.bank.build_packs --all --mode buzzer
node scripts/bank/review.js
```
Expected: `pytest` vert ; import sans erreur (difficultés normalisées) ; packs QCM et buzzer générés ; `review.html` regénéré.

- [ ] **Step 4: No commit.**

---

## Notes d'exécution

- Aucune commande `git add` / `git commit` ne doit être lancée (contrainte utilisateur).
- Lancer pytest et les scripts `python -m scripts.bank.*` depuis le dossier `backend/`.
- Le script de réécriture des fichiers `aigen` (Task 4) est jetable — ne pas le laisser dans le repo.
