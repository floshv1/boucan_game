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
