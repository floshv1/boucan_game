"""Canonical theme taxonomy + a lightweight keyword classifier.

Themes mirror OpenQuizzDB's 22 broad categories so OpenQuizzDB rows map 1:1 and
JsonQuizz / AI rows can be classified into the same space. The classifier is
best-effort (keyword scoring); unmatched questions fall back to ``culture``
(culture générale). OpenQuizzDB and AI imports pass an explicit theme and skip it.
"""

from __future__ import annotations

import re
import unicodedata

THEMES: tuple[str, ...] = (
    "animaux",
    "archeologie",
    "arts",
    "bd",
    "celebrites",
    "cinema",
    "culture",
    "gastronomie",
    "geographie",
    "histoire",
    "informatique",
    "internet",
    "litterature",
    "loisirs",
    "monde",
    "musique",
    "nature",
    "quotidien",
    "sciences",
    "sports",
    "television",
    "tourisme",
    # Extensions hors taxonomie OpenQuizzDB (thèmes demandés)
    "jeux_video",
    "series",
    "drapeaux",
    "rebus",
    "quatre_images",
)

# theme -> keywords (accent-insensitive, matched on word boundaries). Order/length
# don't matter; the theme with the most keyword hits wins.
_KEYWORDS: dict[str, list[str]] = {
    "animaux": ["animal", "animaux", "chat", "chien", "oiseau", "poisson", "mammifere",
                "insecte", "reptile", "espece", "felin", "race", "patte", "queue"],
    "geographie": ["pays", "capitale", "ville", "fleuve", "montagne", "continent", "ocean",
                   "mer", "region", "frontiere", "drapeau", "ile", "departement"],
    "histoire": ["guerre", "roi", "reine", "empereur", "revolution", "siecle", "bataille",
                 "antiquite", "moyen age", "napoleon", "dynastie", "traite", "histoire"],
    "sciences": ["atome", "molecule", "chimie", "physique", "element", "energie", "cellule",
                 "planete", "gravite", "formule", "symbole chimique", "math", "nombre", "calcul"],
    "musique": ["chanson", "groupe", "album", "chanteur", "chanteuse", "musique", "guitare",
                "piano", "rap", "rock", "concert", "instrument", "note de musique"],
    "cinema": ["film", "acteur", "actrice", "realisateur", "oscar", "cinema", "personnage de film",
               "saga", "hollywood", "long metrage", "pixar", "studio d animation"],
    "jeux_video": ["jeu video", "jeux video", "mario", "luigi", "zelda", "pokemon", "nintendo",
                   "playstation", "xbox", "sega", "console de jeu", "manette", "fortnite",
                   "minecraft", "sonic", "tetris", "jeu d arcade", "game boy"],
    "television": ["serie", "emission", "television", "tele", "presentateur", "chaine",
                   "episode", "telerealite"],
    "sports": ["sport", "football", "tennis", "rugby", "olympique", "champion", "equipe",
               "match", "joueur", "but", "ballon", "course", "cyclisme", "basket"],
    "litterature": ["roman", "auteur", "ecrivain", "livre", "poete", "poesie", "litterature",
                    "personnage de roman", "prix nobel de litterature"],
    "gastronomie": ["plat", "cuisine", "fromage", "vin", "recette", "ingredient", "gastronomie",
                    "dessert", "boisson", "chocolat", "sucre", "epice"],
    "arts": ["peintre", "tableau", "peinture", "peint", "fresque", "sculpture", "sculpteur",
             "sculpte", "toile", "statue", "musee", "art", "oeuvre", "renaissance",
             "courant artistique", "exposition"],
    "informatique": ["ordinateur", "logiciel", "programmation", "informatique", "processeur",
                     "systeme d exploitation", "code", "octet", "algorithme"],
    "internet": ["internet", "web", "site", "reseau social", "navigateur", "url", "email",
                 "google", "youtube", "wifi"],
    "nature": ["plante", "arbre", "fleur", "foret", "climat", "volcan", "nature", "ecologie",
               "mineral", "roche"],
    "bd": ["bande dessinee", "bd", "manga", "comics", "asterix", "tintin", "super heros",
           "marvel", "dc"],
    "celebrites": ["acteur", "star", "celebrite", "people", "milliardaire", "mannequin"],
    "corps": ["corps humain", "organe", "muscle", "os", "sante", "maladie", "medecine"],
    "tourisme": ["monument", "tour eiffel", "voyage", "tourisme", "hotel", "plage", "vacances"],
}


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def classify(question: str, answer: str = "", choices: list[str] | None = None) -> str:
    """Return the best-matching broad theme, or ``culture`` as a fallback."""
    hay = _norm(" ".join([question, answer, " ".join(choices or [])]))
    best, best_score = "culture", 0
    for theme, words in _KEYWORDS.items():
        score = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", hay))
        if score > best_score:
            best, best_score = theme, score
    # "corps" is a virtual bucket → fold into sciences (no dedicated OpenQuizzDB theme)
    if best == "corps":
        best = "sciences"
    return best if best in THEMES else "culture"
