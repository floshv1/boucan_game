# Banque de questions (FR) → packs

Pipeline pour constituer une grande banque de questions françaises multi-thèmes et
en générer des **packs jouables** que l'app lit sans modification.

```
sources ──► questionbank.db (SQLite) ──► packs/*.json ──► moteur de jeu
            (dédoublonnage, thèmes,        (build_packs)     (inchangé)
             difficulté)
```

La banque (`data/questionbank.db`, configurable via `BANK_DB`) est la **source
canonique**. Les packs en sont une projection ; on peut les régénérer à volonté.
Tout est en lib standard (`sqlite3`) — aucune dépendance nouvelle.

> Lancer les commandes **depuis `backend/`** (avec `uv run` pour l'environnement).

## 1. Alimenter la banque

| Source | Commande | Détail |
|---|---|---|
| **JsonQuizz** (~1140 QCM FR, libre) | `uv run python -m scripts.bank.import_jsonquizz` | Télécharge 3 fichiers GitHub, classe par thème, dédoublonne. |
| **OpenQuizzDB** (22 thèmes, CC BY-SA) | `OPENQUIZZDB_KEY=xxxx uv run python -m scripts.bank.import_openquizzdb --per-theme 8` | Clé gratuite par e-mail (200 appels, 1 question/appel). S'arrête net sur quota. |
| **Génération IA** (le volume) | `uv run python -m scripts.bank.import_aigen` | Charge `scripts/bank/aigen/*.json` (voir format ci-dessous). |
| **Drapeaux** (QCM image) | `uv run python -m scripts.bank.import_flags` | Télécharge ~110 drapeaux libres (flagcdn) dans `media/`, génère des QCM « Quel pays ? ». |

## 2. Générer les packs

```bash
# Un pack QCM + un pack Buzzer par thème ayant ≥ 20 questions, 150 max par pack
uv run python -m scripts.bank.build_packs --all --mode qcm    --min 20 --limit 150
uv run python -m scripts.bank.build_packs --all --mode buzzer --min 20 --limit 150

# Un thème précis
uv run python -m scripts.bank.build_packs --theme histoire --mode qcm --difficulty expert
```

Les packs apparaissent dans `backend/packs/` (tag `banque`) et dans l'éditeur.

## 3. Inspecter la banque

```bash
uv run python -c "from scripts.bank import bank_db; c=bank_db.connect(); \
print(bank_db.total(c)); [print(t,n) for t,n in bank_db.counts_by_theme(c)]"
```

## Atteindre 100+ par thème

JsonQuizz + OpenQuizzDB ne suffisent pas pour 100+ par thème **large**. On complète
avec des lots IA : créer un fichier `scripts/bank/aigen/<theme>_NN.json` puis
relancer `import_aigen` + `build_packs`. Format :

```json
{
  "theme": "histoire",
  "difficulty": "intermediaire",
  "questions": [
    {"question": "…", "choices": ["A", "B", "C", "D"], "answer": "B", "anecdote": "…"}
  ]
}
```

Règles : `theme` ∈ `themes.THEMES` (22 thèmes OpenQuizzDB) ; exactement 4 `choices` ;
`answer` doit figurer dans `choices` ; `difficulty` ∈ `debutant|intermediaire|expert`.
Le dédoublonnage (qhash sur la question normalisée) est automatique entre toutes les
sources.

> ⚠️ Les questions IA doivent être **relues** : un LLM peut se tromper sur des faits.

## Thèmes à base d'images

- **Drapeaux** : entièrement automatisé (voir `import_flags.py`). Chaque question porte
  une `image` (`/media/flag_<cc>.png`) ; la colonne `image` de la banque la transporte
  jusqu'au pack. Le hash de dédoublonnage (`bank_db.dedup_hash`) inclut réponse + image,
  car toutes les questions partagent le même énoncé.
- **Rébus** et **4 images 1 mot** : pas de source libre fiable, et le schéma n'accepte
  qu'**une** image par question. Des packs « scaffold » (mode Buzzer, tag `à compléter`)
  sont créés pour que l'hôte ajoute ses propres images via l'éditeur (pour « 4 images »,
  une image composite par énigme).

## Taxonomie

22 thèmes OpenQuizzDB + extensions demandées : `jeux_video`, `series`, `drapeaux`,
`rebus`, `quatre_images` (voir `themes.THEMES`). `build_packs.py` mappe chaque thème
vers un libellé d'affichage (`THEME_LABELS`).
