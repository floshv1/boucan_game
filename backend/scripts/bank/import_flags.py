"""Build a "Drapeaux" image-QCM theme automatically.

Country names are a curated FR list (offline, robust); flag PNGs are fetched from
flagcdn.com (free). Flags are saved to ``MEDIA_DIR`` (default ``media/``) as
``flag_<cc>.png`` and served by the app at ``/media/flag_<cc>.png``. Each question
is "À quel pays appartient ce drapeau ?" with 4 country-name choices (distractors
preferentially drawn from the same region).

Run from the backend dir:  ``python -m scripts.bank.import_flags``
"""

from __future__ import annotations

import random

import httpx

from game import packs_store
from scripts.bank import bank_db

FLAG = "https://flagcdn.com/w320/{cc}.png"
SOURCE = "flagcdn"
SOURCE_URL = "https://flagcdn.com"

# (ISO 3166-1 alpha-2, nom FR, région) — région sert à choisir des distracteurs plausibles.
COUNTRIES: list[tuple[str, str, str]] = [
    # Europe
    ("fr", "France", "Europe"), ("de", "Allemagne", "Europe"), ("es", "Espagne", "Europe"),
    ("it", "Italie", "Europe"), ("pt", "Portugal", "Europe"), ("gb", "Royaume-Uni", "Europe"),
    ("ie", "Irlande", "Europe"), ("be", "Belgique", "Europe"), ("nl", "Pays-Bas", "Europe"),
    ("lu", "Luxembourg", "Europe"), ("ch", "Suisse", "Europe"), ("at", "Autriche", "Europe"),
    ("dk", "Danemark", "Europe"), ("se", "Suède", "Europe"), ("no", "Norvège", "Europe"),
    ("fi", "Finlande", "Europe"), ("is", "Islande", "Europe"), ("pl", "Pologne", "Europe"),
    ("cz", "Tchéquie", "Europe"), ("sk", "Slovaquie", "Europe"), ("hu", "Hongrie", "Europe"),
    ("ro", "Roumanie", "Europe"), ("bg", "Bulgarie", "Europe"), ("gr", "Grèce", "Europe"),
    ("hr", "Croatie", "Europe"), ("si", "Slovénie", "Europe"), ("rs", "Serbie", "Europe"),
    ("ua", "Ukraine", "Europe"), ("ru", "Russie", "Europe"), ("lt", "Lituanie", "Europe"),
    ("lv", "Lettonie", "Europe"), ("ee", "Estonie", "Europe"), ("al", "Albanie", "Europe"),
    ("mt", "Malte", "Europe"), ("cy", "Chypre", "Europe"),
    # Afrique
    ("ma", "Maroc", "Afrique"), ("dz", "Algérie", "Afrique"), ("tn", "Tunisie", "Afrique"),
    ("eg", "Égypte", "Afrique"), ("ly", "Libye", "Afrique"), ("sn", "Sénégal", "Afrique"),
    ("ci", "Côte d'Ivoire", "Afrique"), ("ml", "Mali", "Afrique"), ("ng", "Nigéria", "Afrique"),
    ("gh", "Ghana", "Afrique"), ("cm", "Cameroun", "Afrique"), ("ke", "Kenya", "Afrique"),
    ("et", "Éthiopie", "Afrique"), ("tz", "Tanzanie", "Afrique"), ("za", "Afrique du Sud", "Afrique"),
    ("zw", "Zimbabwe", "Afrique"), ("ao", "Angola", "Afrique"), ("mg", "Madagascar", "Afrique"),
    ("ne", "Niger", "Afrique"), ("td", "Tchad", "Afrique"), ("bf", "Burkina Faso", "Afrique"),
    ("gn", "Guinée", "Afrique"), ("rw", "Rwanda", "Afrique"), ("ug", "Ouganda", "Afrique"),
    # Asie
    ("cn", "Chine", "Asie"), ("jp", "Japon", "Asie"), ("kr", "Corée du Sud", "Asie"),
    ("kp", "Corée du Nord", "Asie"), ("in", "Inde", "Asie"), ("pk", "Pakistan", "Asie"),
    ("bd", "Bangladesh", "Asie"), ("id", "Indonésie", "Asie"), ("th", "Thaïlande", "Asie"),
    ("vn", "Viêt Nam", "Asie"), ("ph", "Philippines", "Asie"), ("my", "Malaisie", "Asie"),
    ("sg", "Singapour", "Asie"), ("mm", "Birmanie", "Asie"), ("kh", "Cambodge", "Asie"),
    ("np", "Népal", "Asie"), ("lk", "Sri Lanka", "Asie"), ("ir", "Iran", "Asie"),
    ("iq", "Irak", "Asie"), ("sa", "Arabie saoudite", "Asie"), ("ae", "Émirats arabes unis", "Asie"),
    ("il", "Israël", "Asie"), ("tr", "Turquie", "Asie"), ("jo", "Jordanie", "Asie"),
    ("lb", "Liban", "Asie"), ("af", "Afghanistan", "Asie"), ("kz", "Kazakhstan", "Asie"),
    # Amériques
    ("us", "États-Unis", "Amériques"), ("ca", "Canada", "Amériques"), ("mx", "Mexique", "Amériques"),
    ("br", "Brésil", "Amériques"), ("ar", "Argentine", "Amériques"), ("cl", "Chili", "Amériques"),
    ("pe", "Pérou", "Amériques"), ("co", "Colombie", "Amériques"), ("ve", "Venezuela", "Amériques"),
    ("ec", "Équateur", "Amériques"), ("bo", "Bolivie", "Amériques"), ("py", "Paraguay", "Amériques"),
    ("uy", "Uruguay", "Amériques"), ("cu", "Cuba", "Amériques"),
    ("do", "République dominicaine", "Amériques"), ("gt", "Guatemala", "Amériques"),
    ("cr", "Costa Rica", "Amériques"), ("pa", "Panama", "Amériques"), ("jm", "Jamaïque", "Amériques"),
    ("ht", "Haïti", "Amériques"),
    # Océanie
    ("au", "Australie", "Océanie"), ("nz", "Nouvelle-Zélande", "Océanie"), ("fj", "Fidji", "Océanie"),
    ("pg", "Papouasie-Nouvelle-Guinée", "Océanie"),
]


def run() -> None:
    conn = bank_db.connect()
    media = packs_store._media_dir()
    by_region: dict[str, list[str]] = {}
    for _cc, name, region in COUNTRIES:
        by_region.setdefault(region, []).append(name)
    all_names = [name for _cc, name, _r in COUNTRIES]

    inserted = dups = failed = 0
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for cc, name, region in COUNTRIES:
            dest = media / f"flag_{cc}.png"
            if not dest.exists():
                try:
                    img = client.get(FLAG.format(cc=cc))
                    if img.status_code != 200 or not img.content:
                        failed += 1
                        continue
                    dest.write_bytes(img.content)
                except httpx.HTTPError:
                    failed += 1
                    continue

            pool = [n for n in by_region.get(region, []) if n != name]
            if len(pool) < 3:
                pool += [n for n in all_names if n != name and n not in pool]
            choices = [name, *random.sample(pool, 3)]
            random.shuffle(choices)

            # Rows stay distinct despite the shared prompt because the bank's dedup
            # hash includes the answer + image (see bank_db.dedup_hash).
            ok = bank_db.insert_question(
                conn,
                question="À quel pays appartient ce drapeau ?",
                answer=name,
                choices=choices,
                theme="drapeaux",
                difficulty="intermediaire",
                source=SOURCE,
                source_url=SOURCE_URL,
                image=f"/media/flag_{cc}.png",
            )
            inserted += ok
            dups += (not ok)
        conn.commit()
    print(f"[flags] inserted={inserted} duplicates={dups} download_failed={failed}")
    print(f"[bank] total={bank_db.total(conn)}")
    conn.close()


if __name__ == "__main__":
    run()
