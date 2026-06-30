import json
from pathlib import Path

import pytest

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


def test_aigen_files_use_new_difficulty_vocabulary():
    aigen = Path(__file__).resolve().parent.parent / "scripts" / "bank" / "aigen"
    legacy = {"debutant", "intermediaire", "expert"}
    offenders = []
    for path in sorted(aigen.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if str(data.get("difficulty", "")).strip().lower() in legacy:
            offenders.append(path.name)
    assert offenders == [], f"fichiers avec ancien vocabulaire: {offenders}"
