"""Built-in starter packs so a host can play instantly without writing questions.

These are read-only: they always appear in the pack list (flagged ``builtin``)
and cannot be overwritten or deleted (``packs_store`` only writes user packs to
disk). Content is French culture générale, kept light and family-friendly.

Each pack mirrors the on-disk pack shape (see packs_store.save_pack) so the same
``get_pack`` / ``list_packs`` consumers work unchanged. The frozen timestamp keeps
them sorted just below freshly-edited user packs.
"""

from __future__ import annotations

_FROZEN = "2026-01-01T00:00:00+00:00"


def _qcm(question: str, choices: list[str], correct: int, *, bonus: bool = False) -> dict:
    return {
        "question": question,
        "choices": choices,
        "correct": correct,
        "time_limit": 20,
        "points": 1000,
        "bonus": bonus,
        "image": None,
    }


def _buzz(question: str, answer: str, *, points: int = 1, bonus: bool = False) -> dict:
    return {"question": question, "answer": answer, "points": points, "bonus": bonus, "image": None}


_QCM_CULTURE = [
    _qcm("Quelle est la capitale de l'Australie ?", ["Sydney", "Melbourne", "Canberra", "Perth"], 2),
    _qcm("Combien de côtés a un hexagone ?", ["5", "6", "7", "8"], 1),
    _qcm("Qui a peint la Joconde ?", ["Michel-Ange", "Raphaël", "Léonard de Vinci", "Botticelli"], 2),
    _qcm("Quelle planète est la plus proche du Soleil ?", ["Vénus", "Mercure", "Mars", "Terre"], 1),
    _qcm("En quelle année a eu lieu la Révolution française ?", ["1689", "1789", "1815", "1848"], 1),
    _qcm("Quel est l'océan le plus grand ?", ["Atlantique", "Indien", "Arctique", "Pacifique"], 3),
    _qcm("Combien de joueurs dans une équipe de foot sur le terrain ?", ["9", "10", "11", "12"], 2),
    _qcm("Quel gaz les plantes absorbent-elles ?", ["Oxygène", "Azote", "Dioxyde de carbone", "Hélium"], 2),
    _qcm("Quelle est la monnaie du Japon ?", ["Yuan", "Won", "Yen", "Ringgit"], 2),
    _qcm("Quel est le plus long fleuve du monde ?", ["Amazone", "Nil", "Yangtsé", "Mississippi"], 1),
    _qcm("Qui a écrit « Les Misérables » ?", ["Zola", "Hugo", "Balzac", "Flaubert"], 1),
    _qcm("Combien de continents y a-t-il ?", ["5", "6", "7", "8"], 2, bonus=True),
]

_QCM_MUSIQUE = [
    _qcm("Quel groupe a chanté « Bohemian Rhapsody » ?", ["The Beatles", "Queen", "Pink Floyd", "ABBA"], 1),
    _qcm("De quel pays vient le reggae ?", ["Cuba", "Brésil", "Jamaïque", "Sénégal"], 2),
    _qcm("Combien de cordes a une guitare classique ?", ["4", "5", "6", "7"], 2),
    _qcm("Qui est surnommé le « King of Pop » ?", ["Elvis", "Prince", "Michael Jackson", "James Brown"], 2),
    _qcm("Quel instrument a des touches noires et blanches ?", ["Violon", "Piano", "Trompette", "Flûte"], 1),
    _qcm("« Get Lucky » est un titre de quel duo ?", ["Justice", "Daft Punk", "The Chemical Brothers", "Air"], 1),
    _qcm("Quelle chanteuse a sorti l'album « 21 » ?", ["Adele", "Rihanna", "Beyoncé", "Sia"], 0),
    _qcm("Le rap est né dans quelle ville ?", ["Los Angeles", "New York", "Atlanta", "Chicago"], 1),
    _qcm("Combien de symphonies Beethoven a-t-il composées ?", ["5", "7", "9", "12"], 2),
    _qcm(
        "Quel festival a lieu chaque été en Angleterre ?",
        ["Coachella", "Tomorrowland", "Glastonbury", "Sziget"],
        2,
        bonus=True,
    ),
]

_BUZZER_CULTURE = [
    _buzz("Quel est l'élément chimique de symbole « O » ?", "L'oxygène"),
    _buzz("Combien font 7 × 8 ?", "56"),
    _buzz("Quel animal est le roi de la jungle ?", "Le lion"),
    _buzz("Dans quel pays se trouve la tour Eiffel ?", "La France"),
    _buzz("Quelle est la couleur obtenue en mélangeant bleu et jaune ?", "Le vert"),
    _buzz("Qui a découvert la gravité avec une pomme ?", "Isaac Newton"),
    _buzz("Combien de minutes dans une heure ?", "60"),
    _buzz("Quel est le plus grand désert chaud du monde ?", "Le Sahara"),
    _buzz("Quelle planète est surnommée la planète rouge ?", "Mars"),
    _buzz("Combien de cœurs a une pieuvre ?", "Trois", points=2, bonus=True),
]


# Full pack dicts (same shape as on-disk packs).
BUILTIN_PACKS: list[dict] = [
    {
        "id": "builtin-qcm-culture",
        "builtin": True,
        "created_at": _FROZEN,
        "updated_at": _FROZEN,
        "name": "Culture générale (QCM)",
        "description": "Pack prêt à jouer — culture générale.",
        "tags": ["prêt à jouer"],
        "mode": "qcm",
        "items": _QCM_CULTURE,
    },
    {
        "id": "builtin-qcm-musique",
        "builtin": True,
        "created_at": _FROZEN,
        "updated_at": _FROZEN,
        "name": "Musique (QCM)",
        "description": "Pack prêt à jouer — autour de la musique.",
        "tags": ["prêt à jouer"],
        "mode": "qcm",
        "items": _QCM_MUSIQUE,
    },
    {
        "id": "builtin-buzzer-culture",
        "builtin": True,
        "created_at": _FROZEN,
        "updated_at": _FROZEN,
        "name": "Culture générale (Buzzer)",
        "description": "Pack prêt à jouer — questions rapides au buzzer.",
        "tags": ["prêt à jouer"],
        "mode": "buzzer",
        "items": _BUZZER_CULTURE,
    },
]

_BY_ID = {p["id"]: p for p in BUILTIN_PACKS}


def builtin_summaries() -> list[dict]:
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "mode": p["mode"],
            "count": len(p["items"]),
            "tags": p.get("tags", []),
            "updated_at": p["updated_at"],
            "builtin": True,
        }
        for p in BUILTIN_PACKS
    ]


def get_builtin(pack_id: str) -> dict | None:
    return _BY_ID.get(pack_id)
