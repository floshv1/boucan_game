# Bloc B (tranche 1) — Ingestion OpenTriviaQA avec traduction + filtre qualité

Date : 2026-06-30
Statut : validé (design)

## Contexte

Le Bloc A a standardisé la difficulté (`facile/moyen/difficile/inconnu`) et lié les points à la
difficulté. Le Bloc B vise à **augmenter le volume** de la banque (`backend/data/questionbank.db`)
en ingérant des datasets externes. Plutôt que câbler 5 sources d'un coup (risque élevé : on ignore
encore si du trivia anglais traduit est bon pour un public français), cette tranche livre **une seule
source bout-en-bout — OpenTriviaQA** — pour valider la chaîne et la qualité avant d'étendre.

Sources reportées aux tranches suivantes : Hugging Face, Kaggle (auth API), KCulture / jklm PopSauce
(média, mal définies).

## Principe directeur

Le vrai goulot n'est pas la traduction mais la **pertinence** : beaucoup de questions OpenTriviaQA sont
très US-centrées et inadaptées même bien traduites. Donc Claude fait **deux choses en un appel** :
traduire ET juger si la question mérite d'être gardée pour un public français.

On **traduit une seule fois** (cache + stockage en base) ; le jeu ne traduit jamais au runtime.

## Architecture

```
OpenTriviaQA ──fetch──▶ records ──normalize──▶ QuestionDraft(EN) ──translate+filter──▶ QuestionDraft(FR)
 (repo GitHub)  (.txt)            (format commun)      (Claude + cache)         ──classify+insert──▶ bank_db
                                                                                   (dédup qhash)
```

Quatre unités, chacune testable isolément :

- `backend/scripts/bank/translate.py` — traduction + filtre qualité, avec cache persistant. Interface
  isolée (échangeable DeepL plus tard).
- `backend/scripts/bank/opentriviaqa.py` — fetch + parse du format OpenTriviaQA → `list[QuestionDraft]`.
- `backend/scripts/bank/ingest_opentriviaqa.py` — orchestration (CLI) : fetch → translate/filter →
  classify → insert, avec compteurs.
- Ajout d'un thème `religion` dans `themes.py` + `build_packs.py`.

### `QuestionDraft` (dataclass commune, dans `opentriviaqa.py` ou un petit `drafts.py`)

```python
@dataclass
class QuestionDraft:
    question: str
    answer: str
    choices: list[str]      # 4 choix, answer inclus
    category: str           # catégorie source OpenTriviaQA (pour le mapping thème)
    source_url: str
```

## Section 1 — `translate.py` (traduction + filtre qualité)

Interface publique :

```python
def translate_question(draft: QuestionDraft) -> TranslatedQuestion | None:
    """Traduit + juge une question. Retourne None si Claude la rejette (`garder=false`)."""
```

`TranslatedQuestion` : `question, answer, choices[4], difficulty` (vocab Bloc A), en français.

- **Un appel Claude par question**, via `httpx` brut sur l'API Messages (`POST
  https://api.anthropic.com/v1/messages` ; headers `x-api-key`, `anthropic-version: 2023-06-01`,
  `content-type: application/json`). Modèle par défaut `claude-sonnet-4-6` (bon compromis qualité/coût
  pour la traduction nuancée + le jugement de pertinence), surchargé par env `TRANSLATE_MODEL`
  (ex. `claude-haiku-4-5` pour réduire le coût). `max_tokens` ~1024, non-streaming (réponse courte).
- **Sortie JSON stricte** via `output_config.format` (`type: "json_schema"`, `additionalProperties:
  false`), garantissant un premier bloc texte JSON valide. Schéma :
  `{"garder": bool, "question": str, "choix": [str...], "bonne_reponse": str,
  "difficulte": enum("facile","moyen","difficile")}`. Le JSON-schema ne peut pas imposer « exactement
  4 choix » → le code valide la longueur des choix (= 4) et que `bonne_reponse ∈ choix`, sinon rejet.
- **`garder=false`** quand la question est trop spécifiquement américaine, intraduisible, ambiguë, ou
  de mauvaise qualité → la fonction retourne `None`.
- **Cohérence** : `bonne_reponse` doit être l'un des `choix` ; sinon la question est rejetée (sécurité).
- **Cache persistant** : `data/translation_cache.json` (chemin via env `TRANSLATION_CACHE`, défaut
  `data/translation_cache.json`). Clé = SHA-1 du texte EN de la question. Valeur = le JSON Claude
  (y compris les rejets, pour ne pas re-juger). Lu au démarrage, réécrit après chaque nouvelle
  traduction.
- **Clé API** : lit `ANTHROPIC_API_KEY`. Absente → `RuntimeError` avec message clair. Appel via `httpx`
  (déjà dépendance) sur l'API Messages — **pas de nouveau package**.
- **Garde-fou coût** : l'appelant (l'orchestrateur) gère `--limit` ; `translate.py` n'appelle Claude
  que sur un cache-miss.

## Section 2 — `opentriviaqa.py` (fetch + parse)

- Source : repo `uberspot/OpenTriviaQA`, dossier `categories/` (fichiers texte par catégorie).
- Format par bloc :
  ```
  #Q <question>
  ^ <bonne réponse>
  A <choix>
  B <choix>
  C <choix>
  D <choix>
  ```
  (lignes vides entre blocs). Le parser tolère un nombre de choix ≠ 4 et les ignore (on ne garde que
  les blocs à exactement 4 choix dont `^` est l'un d'eux).
- `fetch_categories() -> dict[str, str]` : télécharge le texte brut de chaque catégorie via `httpx`
  (URLs raw GitHub). `parse_category(text, category) -> list[QuestionDraft]`.
- Réseau isolé du parsing : `parse_category` est pur (testable sur une chaîne fixe sans réseau).

## Section 3 — Thème `religion` + mapping catégories

- `themes.py` : ajouter `"religion"` au tuple `THEMES` ; ajouter des mots-clés
  (`["religion", "dieu", "eglise", "bible", "coran", "priere", "saint", "pape", "temple", "boudha"]`)
  dans `_KEYWORDS` pour que `classify()` le détecte.
- `build_packs.py` : ajouter `"religion": "Religion"` dans `THEME_LABELS`.
- Mapping catégorie OpenTriviaQA → thème, dans `ingest_opentriviaqa.py` :
  ```
  animals→animaux, geography→geographie, history→histoire, literature→litterature,
  movies→cinema, music→musique, science-technology→sciences, sports→sports,
  television→television, video-games→jeux_video, world→monde, people/celebrities→celebrites,
  religion-faith→religion, hobbies→loisirs, humanities→arts, entertainment/general/for-kids/
  brain-teasers→ (repli) classify() sur le texte FR
  ```
  Repli général : si la catégorie n'est pas mappée, `themes.classify(question_fr, answer_fr, choices_fr)`.

## Section 4 — `ingest_opentriviaqa.py` (orchestration CLI)

```
python -m scripts.bank.ingest_opentriviaqa --limit 100        # tranche d'essai
python -m scripts.bank.ingest_opentriviaqa                    # tout le repo
python -m scripts.bank.ingest_opentriviaqa --category geography
```

Boucle : pour chaque draft (jusqu'à `--limit`) → `translate_question` (cache) → si `None`, compteur
rejets ; sinon `classify`/mapping thème → `bank_db.insert_question(source="opentriviaqa", ...)`.
Compteurs finaux : `importées / rejetées (Claude) / doublons (qhash) / invalides / coût appels`.

## Tests

- `translate.py` : avec un client Claude **mocké** (monkeypatch de la fonction d'appel HTTP) —
  réponse `garder=true` → `TranslatedQuestion` correcte ; `garder=false` → `None` ;
  `bonne_reponse` hors `choix` → `None` ; **cache hit ne rappelle pas le client** (compteur d'appels) ;
  `ANTHROPIC_API_KEY` absente → `RuntimeError`.
- `opentriviaqa.py` : `parse_category` sur un texte fixe → bons `QuestionDraft` ; bloc à 3 choix ignoré ;
  `^` absent des choix ignoré. (Pas de réseau dans les tests.)
- `themes.py` : `"religion"` ∈ `THEMES` ; `classify("Quel est le livre saint de l'islam ?", "Le Coran")`
  → `"religion"`.
- `ingest` : avec `opentriviaqa.parse_category` et `translate_question` mockés + `BANK_DB` temporaire →
  N insérées, rejets comptés, doublons dédupliqués.

## Vérification end-to-end

```
cd backend
export ANTHROPIC_API_KEY=...        # (PowerShell : $env:ANTHROPIC_API_KEY="...")
python -m scripts.bank.ingest_opentriviaqa --limit 100
node scripts/bank/review.js
# ouvrir review.html, relire la qualité FR des questions source=opentriviaqa
pytest
```
Critère de succès : les 100 questions traduites sont lisibles, pertinentes pour un public français, et
correctement classées. Si oui → on lève `--limit` et on planifie la tranche suivante (Hugging Face).

## Contraintes

- Aucune commande git (commit/branche) — contrainte projet récurrente.
- Français uniquement.
- Aucun nouveau package : traduction via `httpx` sur l'API Anthropic Messages.
- Vocabulaire difficulté + points : ceux du Bloc A.
- Le cache de traduction et la `BANK_DB` ne doivent jamais être re-traduits inutilement (idempotence).

## Hors scope (tranches ultérieures)

- Hugging Face, Kaggle, KCulture, jklm PopSauce.
- Génération de distracteurs pour des sources sans choix (OpenTriviaQA en fournit déjà).
- Repli DeepL (l'interface `translate.py` le permettra sans refonte).
