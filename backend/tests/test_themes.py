from scripts.bank.themes import classify


def test_classify_detects_other_themes():
    assert classify("Quelle est la capitale de la France ?", "Paris") == "geographie"


def test_classify_detects_jeux_video():
    assert classify("Quel plombier est la mascotte de Nintendo ?", "Mario") == "jeux_video"
    assert classify("Quel jeu vidéo de Mojang permet de construire en cubes ?", "Minecraft") == "jeux_video"


def test_classify_detects_arts():
    assert classify("Qui a peint la Joconde ?", "Léonard de Vinci") == "arts"
    assert classify("Qui a sculpté la statue du David ?", "Michel-Ange") == "arts"
