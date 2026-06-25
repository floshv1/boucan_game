# Spec — Phase 2 : Mode QCM (style Kahoot)

> Statut : design validé, prêt pour le plan d'implémentation.
> Phase 2 du `cahier-des-charges.md` (§4.3, §10, §12, §13, §16, §19).

## Contexte

La Phase 1 (mode Buzzer + itération 2 : écran TV partagé, liste de rounds préparée,
Docker) est en place et testée. Cette phase ajoute le **mode QCM** : 4 choix sur le
téléphone, timer serveur, points selon la vitesse, révélation collective, classement
automatique. Objectif : retrouver le rythme d'un Kahoot pour des soirées maison (5–15
joueurs), en réutilisant l'infra temps réel existante (sessions en mémoire, WebSocket,
rôles host/player/tv, filtrage des réponses par rôle).

## Décisions validées (avec l'utilisateur)

1. **Flux séparé du buzzer.** Une partie est soit 100% Buzzer, soit 100% QCM ; le mode
   est choisi au lobby. La liste préparée est homogène. La logique buzzer n'est pas
   modifiée.
2. **Points = vitesse Kahoot + bonus de série**, plafond de série **+50%**.
3. **Timer serveur**, auto-révélation à l'expiration **ou** quand tous les connectés ont
   répondu ; l'hôte peut forcer **Révéler** ou **Passer**.
4. **Classement intermédiaire dédié** (état `SCOREBOARD`) entre chaque question, avec
   indicateurs de montée/descente ▲/▼.
5. **Écran de configuration de partie** au lancement (mode, réglages QCM, éditeur de
   questions, joueurs connectés, QR de join).

## Architecture

**Approche retenue : module QCM isolé.** Un nouveau module **pur** `game/qcm.py`
(au même titre que `game/engine.py`) contient toute la logique QCM (transitions, calcul
des points, payloads filtrés) et renvoie des `Outbound` ; il ne touche jamais au réseau.
La **tâche timer** (compte à rebours serveur) vit dans la couche async (`main.py` /
`ws/manager.py`), seule responsable des effets de bord temporels. Le code buzzer existant
reste inchangé. Frontière nette, testable indépendamment, faible risque.

### Machine à états (extension de cahier §12)

```
LOBBY ──(start_qcm)──► QUESTION_ACTIVE ──(timeout | tous répondu | "reveal")──► REVEAL
  ▲                          │                                                    │
  │                          └──("skip" = reveal sans points)──► REVEAL          │ ("next")
  │                                                                               ▼
  └──────────("next", plus de questions ⇒ GAME_END)──────── SCOREBOARD ◄──────────┘
                                                               │ ("next", question suivante)
                                                               └──► QUESTION_ACTIVE
```

Nouveaux états `GameState` : `QUESTION_ACTIVE`, `REVEAL`, `SCOREBOARD`, `GAME_END`.
Les états buzzer (`LOBBY`, `BUZZER_OPEN`, `BUZZED`) sont conservés. Tout événement reçu
dans un état qui ne l'autorise pas est **ignoré et loggé** (comme le buzzer).

## Modèle de données (`game/models.py`)

```python
class GameMode(StrEnum):
    BUZZER = "buzzer"
    QCM = "qcm"

# GameState += QUESTION_ACTIVE, REVEAL, SCOREBOARD, GAME_END

@dataclass
class QcmRound:                # une question préparée
    question: str
    choices: list[str]         # exactement 4
    correct: int               # index 0..3 — jamais envoyé aux joueurs/TV avant REVEAL
    time_limit: int = 20       # secondes
    points: int = 1000         # base

@dataclass
class QcmAnswer:               # réponse d'un joueur à la question courante
    choice: int                # index choisi dans l'ordre PRÉSENTÉ
    ts: int                    # horodatage serveur de réception (ms)
    correct: bool = False      # calculé au REVEAL
    awarded: int = 0           # calculé au REVEAL
```

**Champs ajoutés à `Session`** :

- `mode: GameMode = GameMode.BUZZER`
- `qcm_shuffle_questions: bool = False`, `qcm_shuffle_choices: bool = False`
- `qcm_rounds: list[QcmRound] = []`, `qcm_index: int = -1`
- `question_started_at: int = 0`, `question_ends_at: int = 0`
- `answers: dict[str, QcmAnswer] = {}` (par player_id, pour la question courante)
- `presented_order: list[int] = []` (permutation des choix présentés quand
  `qcm_shuffle_choices` est actif ; identité sinon)

**Champs ajoutés à `Player`** : `streak: int = 0`, `last_rank: int = 0`.

### Mélange (shuffle)

- `qcm_shuffle_questions` : l'ordre de `qcm_rounds` est mélangé **une fois** au
  `start_qcm` (pas à chaque chargement, pour rester déterministe pendant la partie).
- `qcm_shuffle_choices` : à l'ouverture de chaque question, on tire une permutation
  `presented_order` des indices `[0,1,2,3]`. Les `choices` envoyés suivent cet ordre ;
  l'`answer.choice` reçu est un index dans l'ordre présenté, re-mappé vers l'index
  d'origine pour la comparaison à `correct`. Si désactivé, `presented_order = [0,1,2,3]`.

**Convention d'index côté client.** Tout ce qui est exposé aux clients est dans l'**ordre
présenté** : les `choices` de `question_start`, le `correct` (host dans `question_start`, et
tous au `reveal`) et la `distribution` du `reveal` sont **tous** exprimés en index présenté,
afin que l'UI s'aligne sans re-mapping. Le serveur ne convertit en index d'origine qu'en
interne pour comparer à `QcmRound.correct`.

## Calcul des points (au REVEAL, 100% serveur — cahier §16)

Pour chaque joueur ayant une `QcmAnswer` correcte :

1. **Facteur vitesse** `f = clamp(1 − (t / limite) / 2, 0.5, 1)` où
   `t = clamp((answer.ts − question_started_at) / 1000, 0, limite)` en secondes.
2. **Bonus de série** `mult = 1 + min((streak_after − 1) × 0.10, 0.50)` où
   `streak_after` = série après incrément (1ʳᵉ bonne = +0%, 2ᵉ = +10%, …, **plafond +50%**
   à partir de 6 d'affilée).
3. **Attribué** `awarded = round(points × f × mult)`. Sinon `awarded = 0`.
4. **Série** : `streak += 1` si correct ; **`streak = 0`** si mauvaise réponse **ou pas de
   réponse**.

`skip` (Passer) : on passe à REVEAL, on **révèle** la bonne réponse mais **aucun point
n'est attribué** et **les séries ne sont pas touchées**.

Exemple : question 1000 pts, limite 20s, joueur en série de 3 (mult 1.20), répond juste à
4s → `f = 1 − (4/20)/2 = 0.90` → `round(1000 × 0.90 × 1.20) = 1080` pts.

## Logique pure (`game/qcm.py`)

Fonctions (signatures indicatives), renvoyant `list[Outbound]` :

- `set_qcm_rounds(session, items, *, shuffle_questions, shuffle_choices) -> [...]`
  (LOBBY only ; passe `session.mode = QCM` ; émet `prepared_qcm` **host-only** + état).
- `start_qcm(session, now) -> [...]` : applique le mélange des questions, charge la
  question 0.
- `load_question(session, index, now) -> [...]` : `QUESTION_ACTIVE`,
  `question_started_at = now`, `question_ends_at = now + limite×1000`, calcule
  `presented_order`, vide `answers`, émet `question_start` (filtré) + `qcm_progress`.
- `answer_submit(session, player_id, choice, now) -> [...]` : `QUESTION_ACTIVE` only,
  idempotent (1 par question), enregistre `QcmAnswer`. Émet `qcm_progress`. Signale au
  caller si **tous les joueurs connectés ont répondu** (→ la couche async révèle).
- `reveal(session, *, award=True) -> [...]` : `QUESTION_ACTIVE → REVEAL`, calcule
  correct/awarded, applique scores et séries (si `award`), émet `reveal` +
  `player_list`.
- `to_scoreboard(session) -> [...]` : `REVEAL → SCOREBOARD`, calcule rangs + deltas vs
  `last_rank`, met à jour `last_rank`, émet `scoreboard`.
- `next_(session, now) -> [...]` : depuis `SCOREBOARD`, charge la question suivante ou
  passe à `GAME_END` (podium) s'il n'y en a plus.
- `all_answered(session) -> bool` : helper (tous les `connected` ont répondu).
- `state_sync_payload(session, *, role)` : section QCM du `state_sync` (filtrée).

`all_answered` ne compte que les joueurs **connectés** (un joueur déconnecté ne bloque pas
la révélation).

## Protocole WebSocket (cahier §13)

**Client → serveur**

- `answer_submit { choice: 0..3 }` (joueur). Le serveur date la réception. 1 par question,
  idempotent. Réponse hors `QUESTION_ACTIVE` ignorée.
- `host_action` nouvelles actions (host only) : `set_qcm_rounds {rounds, shuffle_questions,
  shuffle_choices}`, `start_qcm`, `reveal`, `skip`, `next`. La couche WS route chaque
  action vers `engine` (buzzer) ou `qcm` selon l'action / le `mode`.

**Serveur → clients** (filtrés par rôle — `correct` **jamais** aux joueurs/TV avant REVEAL)

| Type | Cible | Payload |
|---|---|---|
| `question_start` | broadcast | `{index, total, question, choices[4], time_limit, ends_at, points}` ; `correct` **uniquement** pour l'hôte |
| `qcm_progress` | broadcast | `{answered, total}` — `total` = joueurs **connectés** ; jamais qui ni quoi |
| `reveal` | broadcast | `{correct, distribution:[n0,n1,n2,n3], deltas:{player_id: pts}}` |
| `scoreboard` | broadcast | `{players:[{id, pseudo, score, rank, delta}]}` (`delta` = `last_rank − rank`) |
| `game_end` | broadcast | `{podium:[≤3, ex-aequo au même rang], players:[…]}` |
| `prepared_qcm` | **host** | liste préparée complète **avec `correct`** (comme `prepared_rounds`) |

- **Acquittement `answer_submit`** : le joueur reçoit un retour léger (verrouillage de son
  choix) ; les autres ne voient que `qcm_progress`.
- **Filtrage** : `correct` est dans `question_start` host-only et dans `reveal` (broadcast).
  `distribution` n'est diffusée qu'au REVEAL.

### Synchronisation du timer

`question_start` porte `ends_at` (ms serveur). Chaque client affiche le compte à rebours en
local à partir de `ends_at` (pas de flux seconde par seconde). La couche async planifie une
tâche `asyncio` par session qui appelle `reveal` à `ends_at` ; elle est **annulée** si tous
ont répondu ou si l'hôte force `reveal`/`skip`/`next`. Une seule tâche timer active par
session (annulation de la précédente avant d'en créer une nouvelle).

### Reconnexion (cahier §13, §19)

`state_sync` est étendu pour porter, en mode QCM, la question courante filtrée selon le
rôle + `ends_at` + l'état (et le podium si `GAME_END`). Un joueur qui rafraîchit pendant une
question retombe sur la bonne question avec le timer restant ; sa `QcmAnswer` déjà
enregistrée reste verrouillée.

## Sécurité (cahier §16)

- `correct` n'est jamais envoyé aux rôles `player`/`tv` avant `REVEAL` (filtrage dans
  `question_start` et `state_sync`, comme la réponse buzzer).
- `prepared_qcm` (qui contient les bonnes réponses) est **host-only**.
- Les points sont calculés **côté serveur** à partir de l'horodatage de réception ; un
  client ne peut pas s'auto-attribuer de points ni falsifier sa vitesse.

## Frontend

Réutilise `useGameSocket` (rôles host/player/tv déjà en place), `JoinCard`, `Scoreboard`,
les couleurs du thème. Nouveaux types dans `lib/types.ts` (QcmRound côté éditeur, payloads
`question_start`/`reveal`/`scoreboard`/`game_end`, état QCM dans le snapshot).

### A. Écran de configuration (lobby hôte) — point d'entrée

- **Mode** Buzzer / QCM (toggle). Buzzer → éditeur actuel ; QCM → éditeur QCM.
- **Réglages QCM** : temps par défaut, points de base (pré-remplissent les nouvelles
  questions), `[ ] Mélanger l'ordre des questions`, `[ ] Mélanger la position des réponses`.
- **Éditeur de question QCM** : énoncé, 4 choix, sélection de la bonne réponse (radio),
  temps, points ; ajout/suppression/édition de questions (même ergonomie que la liste
  buzzer actuelle).
- **Joueurs connectés** en direct + **QR de join**.
- **Démarrer** → `set_qcm_rounds` (avec réglages) puis `start_qcm`.
- Repopulation depuis `prepared_qcm` à la reconnexion de l'hôte (comme `prepared_rounds`).

### B. Hôte en jeu (QCM)

Question + 4 choix avec la **bonne réponse surlignée** (hôte seul), compte à rebours,
compteur **« answered/total »**, boutons **Révéler maintenant / Passer**, puis **Suivant**.
Scoreboard latéral avec ajustement manuel (±) conservé. Badge « Question n/total ».

### C. Joueur (QCM) — mobile-first

4 **gros boutons colorés** (rouge/bleu/jaune/vert) avec le texte du choix, **verrouillage**
après le tap, compte à rebours. Au REVEAL : **✓/✗** plein écran + points gagnés + série en
cours. Entre les questions (`SCOREBOARD`) : écran d'attente avec son rang. À `GAME_END` :
sa place finale. Réutilise l'esthétique tactile du buzzer.

### D. TV (QCM) — écran partagé `/tv/[code]`

Question + 4 choix en grand avec le timer et le **compteur de réponses** (sans dévoiler
qui/quoi). Au REVEAL : bonne réponse surlignée + **histogramme de répartition**. À
`SCOREBOARD` : **classement animé** avec ▲/▼. À `GAME_END` : **podium top 3**. La bonne
réponse n'apparaît jamais avant le REVEAL. La page TV gère désormais les deux modes (buzzer
existant + QCM) selon l'état reçu.

## Cas limites (cahier §19)

- Joueur qui se déconnecte pendant une question → ne bloque pas `all_answered` ; pas de
  réponse ⇒ série remise à 0 au REVEAL.
- Joueur qui rejoint **en cours de question** → intégré ; il peut répondre s'il arrive avant
  le REVEAL, sinon il entre au prochain round (score 0, série 0).
- Deux joueurs même pseudo → suffixe automatique (déjà géré).
- Égalité au podium / scoreboard → ex-aequo au même rang (déjà géré par `_ranked`).
- Reconnexion après `GAME_END` → renvoie le podium via `state_sync`.
- `answer_submit` après le REVEAL ou en double → ignoré.
- Liste QCM vide → `start_qcm` refusé (bouton Démarrer désactivé tant que 0 question).

## Tests (TDD sur `game/qcm.py`, comme `engine.py`)

- Calcul des points : facteur vitesse aux bornes (0s ⇒ ~100%, fin ⇒ 50%), plafond de série
  à +50%, remise à 0 sur mauvaise/absence de réponse, `skip` n'attribue rien.
- Idempotence d'`answer_submit`, rejet hors `QUESTION_ACTIVE`.
- `all_answered` ignore les déconnectés ; déclenche la révélation.
- `correct` absent des payloads players/TV (`question_start`, `state_sync`) ; présent pour
  l'hôte et dans `reveal`.
- Shuffle des choix : re-mapping correct de l'index présenté vers l'index d'origine.
- Transitions QUESTION_ACTIVE → REVEAL → SCOREBOARD → question / GAME_END ; deltas de rang.
- Intégration WS (TestClient) : flux complet host+player+tv, timer (révélation via "reveal"
  forcé pour rester déterministe en test), `prepared_qcm` host-only.

## Hors périmètre (rappel)

Blindtest/Spotify (Phase 3), éditeur de packs + DB (Phase 4), podium animé avancé / thèmes
(Phase 5). Le QCM Phase 2 n'a **pas** d'images de question (ajout possible plus tard via
`image_url`), pas de persistance (tout en mémoire, §15).
