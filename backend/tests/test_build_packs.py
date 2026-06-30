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
    assert build_packs._qcm_item(_row("inconnu"))["points"] == 1000


def test_qcm_item_keeps_correct_index_and_choices():
    item = build_packs._qcm_item(_row("moyen"))
    assert item["choices"] == ["Paris", "Lyon", "Nice", "Lille"]
    assert item["correct"] == 0


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
