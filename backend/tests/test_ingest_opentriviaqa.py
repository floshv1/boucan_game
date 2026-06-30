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
    assert ingest_opentriviaqa.theme_for("history", "q", "a", ["a"]) == "histoire"


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
