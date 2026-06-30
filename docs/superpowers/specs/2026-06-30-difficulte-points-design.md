# Bloc A — Difficulté standardisée, points liés, dual buzzer/QCM

Date : 2026-06-30
Statut : validé (design)

## Contexte

La banque de questions (`backend/data/questionbank.db`, gérée par `backend/scripts/bank/bank_db.py`)
utilise aujourd'hui un vocabulaire de difficulté hérité : `debutant / intermediaire / expert / inconnu`.
On veut :

1. Standardiser la difficulté en **facile / moyen / difficile** (+ `inconnu` pour les sources muettes).
2. Lier le **nombre de points** à la difficulté : **1 / 2 / 3** (valeur *par défaut*, ajustable dans l'éditeur).
3. Garantir que chaque question est utilisable **à la fois en buzzer (réponse libre) et en QCM (4 choix)**.

Ce spec couvre uniquement le **bloc A** (le socle). Deux chantiers suivront, dépendant de ce socle :
- **Bloc B** : ingestion de datasets (OpenTriviaQA, Hugging Face, Kaggle, KCulture, jklm.fun/PopSauce) — français uniquement, traduction EN→FR.
- **Bloc C** : extraction automatisée depuis des émissions TV (Culture Clash / Étoiles, La Table des Savoirs / Émilien, etc.) via transcriptions YouTube → LLM.

## Architecture

La difficulté vit dans la **banque** (DB), pas dans les packs jouables. Les packs ne stockent qu'un
nombre de points. Donc le mapping difficulté→points s'applique **au moment de la génération d'un pack**
(`build_packs.py`), pas au runtime du jeu.

```
aigen/*.json ──import──▶ questionbank.db ──build_packs──▶ packs/*.json ──▶ moteur de jeu
   (difficulté)          (difficulté)        (points = f(difficulté))      (points: nombre)
```

## Section 1 — Vocabulaire de difficulté

Fichier : `backend/scripts/bank/bank_db.py`

- Changer `DIFFICULTIES = ("debutant", "intermediaire", "expert", "inconnu")`
  en `("facile", "moyen", "difficile", "inconnu")`.
- Ajouter un mapping de normalisation des valeurs héritées :
  ```python
  _LEGACY_DIFFICULTY = {"debutant": "facile", "intermediaire": "moyen", "expert": "difficile"}

  def normalize_difficulty(value: str) -> str:
      v = (value or "").strip().lower()
      v = _LEGACY_DIFFICULTY.get(v, v)
      return v if v in DIFFICULTIES else "inconnu"
  ```
- `insert_question()` appelle `normalize_difficulty()` au lieu du test `in DIFFICULTIES`
  (ligne 108) → les fichiers `aigen` contenant encore `"intermediaire"` continuent de marcher.
- Migration unique dans `_migrate(conn)` : pour chaque (ancien → nouveau),
  `UPDATE questions SET difficulty=? WHERE difficulty=?`. Idempotent (n'agit que sur les vieilles valeurs).
- Mettre à jour les 16 fichiers `backend/scripts/bank/aigen/*.json` vers le nouveau vocabulaire
  (remplacement du champ `"difficulty"`), pour cohérence lors de la review.

## Section 2 — Points liés à la difficulté

Mapping central dans `bank_db.py` :
```python
DIFFICULTY_POINTS = {"facile": 1, "moyen": 2, "difficile": 3, "inconnu": 1}
```

Fichier : `backend/scripts/bank/build_packs.py`
- `_buzzer_item()` (ligne 50) : `points = DIFFICULTY_POINTS[row["difficulty"]]` au lieu de `1` codé en dur.
- `_qcm_item()` (ligne 35) : `points = DIFFICULTY_POINTS[row["difficulty"]] * 1000` au lieu de `1000` codé en dur.
  → 1000 / 2000 / 3000. Garde intact le scoring QCM (bonus vitesse + série dans `game/qcm.py`,
  qui multiplie `rnd.points`).
- `_qcm_item` / `_buzzer_item` reçoivent déjà `row` (dict) ; `row["difficulty"]` est disponible.

**Valeur par défaut, pas figée** : l'éditeur (`frontend/components/QcmEditor.tsx`,
`BuzzerEditor.tsx`) garde le champ « Points » modifiable par question. Aucun changement frontend requis —
les points sont un simple nombre dans le pack une fois généré.

## Section 3 — Disponibilité buzzer ET QCM

Comportement déjà en place dans `build_packs.py` + `bank_db.fetch()` :
- **QCM** : `fetch(require_choices=True)` → seules les questions à 4 choix.
- **Buzzer** : `fetch(require_choices=False)` → toutes les questions (les choix sont ignorés,
  réponse libre).

Donc toute question stockée avec 4 choix sert automatiquement aux deux modes ; toutes les questions
`aigen` actuelles ont 4 choix → déjà duales. Le bloc A **vérifie** ce comportement (test) et confirme
que le mapping de points fonctionne dans les deux modes. La génération de distracteurs pour de futures
questions « réponse libre seule » relèvera des blocs B/C.

## Tests

- `normalize_difficulty()` : legacy→nouveau, nouveau→inchangé, inconnu→`"inconnu"`.
- Migration `_migrate` : DB avec anciennes valeurs → toutes converties ; relancer = no-op.
- `build_packs` : un pack buzzer issu d'une question `moyen` a `points == 2` ;
  un pack QCM issu d'une question `difficile` a `points == 3000`.
- Dual : une même question à 4 choix produit un item buzzer ET un item QCM valides.

## Vérification end-to-end

```
cd backend
python -m scripts.bank.import_aigen          # réimport (difficultés normalisées)
python -m scripts.bank.build_packs --all --mode qcm
python -m scripts.bank.build_packs --all --mode buzzer
node scripts/bank/review.js                  # regénère review.html pour relire
pytest                                        # suite backend
```

## Hors scope (blocs ultérieurs)

- B : téléchargement/normalisation des datasets externes + traduction EN→FR.
- C : pipeline transcription YouTube → questions.
- Génération de distracteurs pour les questions sans choix.
