# Cahier des charges — Quiz App

Application web de quiz multijoueur en temps réel, hébergée sur le home server, pour jouer avec des amis à la maison.

---

## 1. Vue d'ensemble

**Objectif** : Créer une plateforme de quiz locale permettant à un hôte de gérer des parties depuis un PC/TV, tandis que les joueurs interagissent depuis leur téléphone via le navigateur. Pas de téléchargement d'application, pas de compte requis.

**Public cible** : Groupe d'amis réunis à la maison (5–15 joueurs typiquement).

**Modes inspirés de** : blindtest.gg (blindtest), jklm.fun / squiz (quiz), Kahoot (QCM chronométré).

---

## 2. Architecture réseau

### Scénario A — WiFi maison (recommandé pour les soirées)

Tous les appareils sont connectés au même réseau WiFi domestique. Le serveur est accessible via son IP locale.

```
PC/TV host ──┐
             ├── WiFi maison → Serveur (192.168.x.x:PORT)
Téléphones ──┘
```

- Aucune configuration supplémentaire requise
- L'hôte affiche un QR code ou l'URL sur l'écran principal pour que les joueurs rejoignent facilement

### Scénario B — Accès via Tailscale

Pour jouer à distance (amis pas sur place) ou si le serveur n'est pas accessible sur le réseau local.

```
Joueurs distants → Tailscale network → drum-discus.ts.net:PORT
```

- Nécessite que chaque joueur distant soit invité sur le réseau Tailscale
- Praticable mais moins fluide qu'un simple QR code en soirée

### Recommandation

Pour une soirée, le **Scénario A (WiFi local)** est suffisant et le plus simple. Le serveur reste accessible par IP locale même si Tailscale tourne en parallèle — les deux coexistent sans conflit.

---

## 3. Rôles

### Host (PC ou TV)

- Interface divisée en deux vues :
  - **Vue contrôle** : gérer la session, passer les questions, valider les réponses, voir les buzzes
  - **Vue affichage** (optionnel, plein écran sur TV) : question + scores visibles par tous les joueurs
- Une seule personne est host par session

### Joueur (téléphone)

- Rejoint la session via code ou QR code avec juste un pseudo
- Interface adaptée mobile : gros bouton buzzer, choix QCM lisibles, saisie texte facile
- Voit son score et son rang en temps réel

---

## 4. Modes de jeu

### 4.1 Blindtest

Inspiré de blindtest.gg.

- L'hôte lance un extrait audio (musique, son, dialogue)
- Les joueurs buzzent dès qu'ils pensent connaître la réponse
- Le premier à buzzer a X secondes pour répondre (à l'oral ou en saisie texte)
- Si mauvaise réponse, le buzzer passe au suivant
- Points variables selon la vitesse et le type de réponse (artiste / titre / les deux)

**Champs d'une question blindtest :**
```json
{
  "type": "blindtest",
  "audio_url": "...",
  "answers": ["titre", "artiste"],
  "points": { "titre": 1, "artiste": 1 },
  "hint": "Indice optionnel affiché après X secondes"
}
```

### 4.2 Quiz Buzzer

- Une question textuelle (ou image) est affichée à tous
- Les joueurs buzzent pour répondre à l'oral
- L'hôte valide ou invalide manuellement
- Si invalidé, le buzzer passe au suivant (ou la question est éliminée)

**Champs :**
```json
{
  "type": "buzzer",
  "question": "Texte de la question",
  "image_url": "...",
  "answer": "La réponse correcte (visible uniquement par le host)",
  "points": 2
}
```

### 4.3 QCM (style Kahoot)

- 4 choix affichés simultanément sur le téléphone de chaque joueur
- Temps limité (ex : 20 secondes)
- Points inversement proportionnels au temps de réponse
- La bonne réponse est révélée après le temps écoulé ou quand tous ont répondu

**Champs :**
```json
{
  "type": "qcm",
  "question": "Texte de la question",
  "image_url": "...",
  "choices": ["A", "B", "C", "D"],
  "correct": 2,
  "time_limit": 20,
  "points": 1000
}
```

### 4.4 Texte libre

- Question affichée, les joueurs saisissent leur réponse librement
- Validation automatique (correspondance exacte ou approchée) ou manuelle par le host
- Utile pour des devinettes, des anagrammes, etc.

**Champs :**
```json
{
  "type": "text",
  "question": "Texte de la question",
  "answer": "réponse",
  "fuzzy_match": true,
  "points": 1
}
```

---

## 5. Fonctionnalités Host

| Fonctionnalité | Détail |
|---|---|
| Créer une session | Génère un code à 6 lettres et un QR code |
| Choisir un pack | Charger un fichier JSON ou créer inline |
| Choisir le mode | Blindtest / Buzzer / QCM / Texte libre (ou mix) |
| Lancer une question | Déclenche l'audio, affiche la question, ouvre le buzzer |
| Gérer le buzzer | Voir l'ordre d'arrivée des buzzes avec timestamps |
| Valider/invalider | Confirmer ou rejeter une réponse orale |
| Passer | Passer à la question suivante sans donner de points |
| Révéler la réponse | Afficher la correction sur tous les écrans |
| Tableau des scores | Visible en temps réel pendant la partie |
| Podium de fin | Écran de fin avec les 3 premiers joueurs |
| Exclure un joueur | Retirer un joueur de la session |

---

## 6. Fonctionnalités Joueur

| Fonctionnalité | Détail |
|---|---|
| Rejoindre | Saisir le code ou scanner le QR code + choisir un pseudo |
| Buzzer | Grand bouton central, désactivé si quelqu'un a déjà buzzé |
| QCM | 4 boutons colorés (A/B/C/D), verrouillage après sélection |
| Texte libre | Champ de saisie + envoi |
| Feedback | Animation : ✓ ou ✗ à la révélation de la réponse |
| Score | Score personnel + classement visible à tout moment |
| Waiting screen | Écran d'attente entre les questions avec classement intermédiaire |

---

## 7. Gestion des packs de questions

### Format JSON (import/export)

```json
{
  "name": "Culture générale — Soirée 2025",
  "description": "Mix blindtest et QCM",
  "tags": ["musique", "cinéma", "géographie"],
  "questions": [
    { "type": "blindtest", ... },
    { "type": "qcm", ... },
    { "type": "buzzer", ... }
  ]
}
```

### Éditeur intégré (Phase 4)

- Interface web pour créer et éditer des packs sans éditer du JSON à la main
- Upload d'images et d'audio directement depuis le navigateur
- Prévisualisation de chaque question

### Stockage des médias

- Fichiers audio/image stockés localement sur le serveur
- Référencés par URL relative dans le JSON

---

## 8. Stack technique

| Composant | Technologie | Justification |
|---|---|---|
| Backend | FastAPI (Python) | Déjà utilisé dans le projet discord-bot-api |
| WebSockets | FastAPI WebSockets | Natif, simple, suffisant pour ~15 joueurs |
| Frontend | Next.js (TypeScript) | Déjà utilisé dans discord-bot-web, App Router |
| Base de données | SQLite (dev) / PostgreSQL (prod) | SQLite pour simplifier le démarrage ; PostgreSQL déjà dispo sur le serveur |
| Conteneurisation | Docker + compose.yml | Cohérent avec tous les autres services |
| Réseau Docker | global_network (externe) | Même réseau que les autres services existants |

### Communication temps réel

Protocole : **WebSockets** (pas de polling).

```
Client (Next.js) ←──── WebSocket ────→ Serveur (FastAPI)
```

Messages typiques :
- `player_join` / `player_leave`
- `buzz` (avec timestamp serveur pour arbitrage)
- `question_start` / `question_end`
- `answer_submit`
- `score_update`
- `game_end`

### Ports

| Service | Port |
|---|---|
| Frontend Next.js | 3200 (à définir, hors des ports existants) |
| Backend FastAPI | 8200 (à définir) |

---

## 9. Contraintes et non-objectifs

**Contraintes :**
- Hébergé uniquement sur le home server (pas de cloud)
- Fonctionne hors internet (sauf pour les CDN éventuels)
- Doit tenir sur des téléphones standards (interface mobile-first)
- Pas plus de ~20 joueurs simultanés (pas besoin de scalabilité)

**Non-objectifs (hors scope) :**
- Comptes utilisateurs persistants
- Déploiement public
- Application mobile native
- Système de tournois ou de saisons
- Monétisation

---

## 10. Phases de développement

### Phase 1 — Infra de base + Buzzer

- Gestion de session (création, code, join)
- Connexion WebSocket joueurs ↔ serveur
- Interface host : contrôle de session + liste joueurs
- Interface joueur : pseudo + grand bouton buzzer
- Ordre des buzzes côté serveur (timestamp)
- Score manuel modifiable par le host

### Phase 2 — Mode QCM (Kahoot)

- Affichage des 4 choix sur le téléphone
- Timer côté serveur
- Calcul des points selon vitesse
- Révélation collective de la réponse
- Tableau des scores automatique

### Phase 3 — Blindtest

- Upload et stockage d'audio
- Lecture audio synchronisée depuis le host
- Buzz + réponse texte ou orale
- Points paramétrables par titre/artiste

### Phase 4 — Éditeur de packs

- Interface web CRUD pour créer des packs
- Upload de médias (images, audio)
- Import/export JSON

### Phase 5 — Polish

- Animations et feedback visuels (confettis, buzzer qui tremble, etc.)
- Écran podium de fin
- Thèmes de couleur
- QR code affiché automatiquement au démarrage
- Vue TV (plein écran, grande police, adapté à une TV connectée)

---

## 11. Structure du projet

```
quiz-app/
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── sessions.py
│   │   ├── game.py
│   │   └── packs.py
│   ├── ws/
│   │   └── manager.py        # WebSocket connection manager
│   ├── models/
│   │   └── ...
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   │   ├── host/             # Interface host
│   │   ├── play/             # Interface joueur
│   │   └── editor/           # Éditeur de packs (Phase 4)
│   ├── Dockerfile
│   └── package.json
├── packs/                    # Packs de questions JSON
├── media/                    # Fichiers audio/images uploadés
├── compose.yml
├── cahier-des-charges.md
└── README.md
```

---

# Détails techniques pour la phase de développement

Les sections suivantes (12–22) sont orientées implémentation. Elles s'alignent sur les conventions du repo `home-server` (uv, ruff, loguru, asyncpg, Docker `global_network`).

---

## 12. Machine à états (game lifecycle)

Le serveur est la **seule source de vérité** de l'état de la partie. Chaque session suit une machine à états explicite :

```
LOBBY ──(start_game)──► QUESTION_ACTIVE ──(buzz)──► BUZZED/ANSWERING
  ▲                          │                           │
  │                          │ (timeout/all_answered)    │ (validate/invalidate)
  │                          ▼                           ▼
  └──(next, si questions)── SCOREBOARD ◄──── REVEAL ◄────┘
                             │
                             │ (plus de questions)
                             ▼
                          GAME_END
```

| État | Description | Événements autorisés |
|---|---|---|
| `LOBBY` | Joueurs rejoignent, host configure | `player_join`, `player_leave`, `start_game` |
| `QUESTION_ACTIVE` | Question affichée, buzzer/réponses ouverts | `buzz`, `answer_submit`, `timeout`, `skip` |
| `BUZZED` / `ANSWERING` | Un joueur a la main pour répondre | `validate`, `invalidate`, `timeout` |
| `REVEAL` | Bonne réponse affichée à tous | `next` |
| `SCOREBOARD` | Classement intermédiaire | `next`, `end_game` |
| `GAME_END` | Podium final | `restart`, `back_to_lobby` |

Tout événement reçu dans un état qui ne l'autorise pas est **ignoré** (et loggé).

---

## 13. Protocole WebSocket

### Enveloppe standard

```json
{ "type": "buzz", "payload": { ... }, "ts": 1718900000123 }
```

`ts` est **toujours** le timestamp serveur à l'émission (arbitrage et synchronisation).

### Messages client → serveur

| Type | Émetteur | Payload |
|---|---|---|
| `join` | joueur | `{ code, pseudo, reconnect_token? }` |
| `buzz` | joueur | `{}` (le serveur date la réception) |
| `answer_submit` | joueur | `{ choice }` ou `{ text }` |
| `host_action` | host | `{ action: "start"\|"next"\|"skip"\|"validate"\|"invalidate"\|"reveal"\|"kick", ... }` |
| `ping` | tous | `{}` |

### Messages serveur → clients

| Type | Cible | Payload |
|---|---|---|
| `state_sync` | unicast | état complet (reconnexion) |
| `player_list` | broadcast | liste joueurs + scores |
| `question_start` | broadcast | question (SANS la réponse pour les joueurs) |
| `buzz_locked` | broadcast | qui a buzzé + ordre |
| `reveal` | broadcast | bonne réponse + deltas de score |
| `scoreboard` | broadcast | classement |
| `game_end` | broadcast | podium |
| `error` | unicast | `{ code, message }` |
| `pong` | unicast | `{}` |

### Reconnexion

- À la connexion, le joueur reçoit un `reconnect_token` stocké en `localStorage`
- Après refresh/coupure WiFi, le client renvoie `join` avec ce token → le serveur le rattache à son `player` existant (place + score conservés) et envoie un `state_sync`
- **Heartbeat** : `ping`/`pong` toutes les ~15s ; sans pong après ~30s, le joueur est marqué *disconnected* (pas supprimé tout de suite, pour permettre la reconnexion)

---

## 14. Arbitrage du buzzer (point critique)

C'est le cœur de l'équité du jeu. L'arbitrage est **100% côté serveur** :

- Le timestamp qui compte est celui de **réception du message `buzz` par le serveur**, jamais celui du client (un client peut tricher sur son horloge)
- Le **premier** buzz reçu verrouille la main ; les buzz suivants sont **mis en file** avec leur ordre et le delta en ms par rapport au premier
- **Idempotence** : un même joueur ne peut buzzer qu'une fois par question (buzz suivants ignorés)
- En cas de réponse invalidée par le host, la main passe **au suivant dans la file**
- **Latence WiFi** : sur un réseau local, l'écart est de quelques ms — acceptable pour un usage maison. Pas de compensation de lag complexe en v1 (documenté comme limitation connue)

---

## 15. Modèle de données

### Persisté en base (SQLite dev / PostgreSQL prod)

| Table | Contenu |
|---|---|
| `game_packs` | métadonnées d'un pack (nom, description, tags, type, owner) |
| `questions` | questions liées à un pack (type, contenu, réponse, points, médias) |
| `game_history` *(optionnel)* | historique des parties jouées et scores finaux |

### En mémoire uniquement (état live)

Les **sessions actives**, les **joueurs connectés** et les **scores en cours** vivent dans des structures en mémoire côté serveur (dict indexés par code de session). Ils sont **éphémères** : reset au redémarrage du serveur. Pas de persistance — une partie ne survit pas à un crash, ce qui est acceptable pour l'usage visé.

> Migration possible vers le PostgreSQL existant du serveur (asyncpg, comme discord-bot) si on veut conserver l'historique.

---

## 16. Sécurité & anti-triche (léger, usage maison)

- **Token host secret** généré à la création de session : seul le détenteur peut envoyer des `host_action`. Empêche un joueur d'usurper le rôle host.
- Les **réponses correctes ne sont JAMAIS envoyées aux joueurs** avant l'état `REVEAL` (filtrage du payload `question_start` selon le rôle)
- **Validation côté serveur** des choix QCM et des soumissions (un client ne peut pas s'auto-attribuer des points)
- Pas d'authentification lourde : contexte local de confiance, mais on verrouille le rôle host et l'intégrité des scores

---

## 17. Configuration & variables d'environnement

`.env` / `.env.example` :

```
PORT_BACKEND=8200
PORT_FRONTEND=3200
DATABASE_URL=sqlite:///./quiz.db        # ou postgres en prod
HOST_SECRET_SEED=...                     # base de génération des tokens host
MEDIA_PATH=./media
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://<ip-locale>:8200/auth/spotify/callback
```

- **Détection automatique de l'IP locale** au démarrage pour afficher la bonne URL/QR code au host
- **Ports** : `3200` (front) / `8200` (back) — à vérifier contre les services existants (homeassistant 8124, nextexplorer 8082, vikunja 3456, discord-bot-web 3100) → pas de collision

---

## 18. Conventions de code & outillage (alignées sur le repo)

| Domaine | Convention |
|---|---|
| Backend | `uv` (deps), `ruff check --fix` + `ruff format`, `loguru` (logs), `pytest` (tests) |
| Frontend | Next.js App Router + TypeScript (comme `discord-bot-web`) |
| Conteneurs | `Dockerfile` par service, `compose.yml` (prod, images GHCR) + `compose.dev.yml` (build local) |
| Réseau Docker | `global_network` (externe), comme les autres services |
| Git | hooks via `core.hooksPath .githooks` cohérents avec le repo |

---

## 19. Cas limites à gérer (checklist dev)

- [ ] Joueur qui quitte en pleine question / pendant son tour de buzz → main passée au suivant
- [ ] Host qui se déconnecte → partie figée en attente de reconnexion (timeout configurable) puis abandon
- [ ] Deux joueurs avec le même pseudo → suffixe automatique ou refus
- [ ] Joueur qui rejoint **en cours de partie** → intégré au prochain round (ou spectateur jusqu'au scoreboard)
- [ ] Audio blindtest qui ne charge pas / timeout Spotify → bouton « rejouer » / skip côté host
- [ ] Égalité de score au podium → ex-aequo affichés au même rang
- [ ] Reconnexion après le `GAME_END` → renvoyer directement le podium

---

## 20. Page de création d'assets

Interface web (`/editor`) pour construire des **assets réutilisables**, sauvegardés dans une bibliothèque.

- **Pack de questions** : créer/éditer des questions (QCM, buzzer, texte libre) avec upload image/audio
- **Pack blindtest depuis Spotify** : coller une URL de playlist Spotify → import automatique des titres (titre, artiste, pochette, durée, `spotify_track_id`) via l'API Spotify
- Chaque asset est **sauvegardé dans une bibliothèque** et réutilisable dans plusieurs parties
- L'utilisateur choisit de le garder en **brouillon** ou de l'**ajouter aux assets du jeu** (bibliothèque partagée)
- Prévisualisation de chaque question avant sauvegarde

---

## 21. Composition d'une partie (game builder)

Avant de lancer, le host **assemble une partie** à partir de plusieurs assets de la bibliothèque.

- Exemple : `1 pack blindtest Spotify` + `1 pack de questions QCM` ajoutés à la même partie
- Les contenus des packs sélectionnés sont **fusionnés** dans une seule file de jeu
- **Mode de mélange choisi au lancement** (le host décide à chaque partie) :
  - **Aléatoire global** : toutes les questions (musique + quiz) mélangées, n'importe quel ordre — une question de n'importe quel pack peut « sortir » à tout moment
  - **Par blocs / rounds** : round musique d'abord, puis round questions (chaque pack reste groupé)
- Paramètres de partie : nombre de questions à tirer, pondération des points par type, durée des timers

---

## 22. Intégration Spotify

**Décision actée** : le host a Spotify Premium → **Spotify Web Playback SDK** comme méthode principale de lecture.

### Méthode retenue — Spotify Web Playback SDK

- Lecture des **morceaux complets** directement dans le navigateur du host
- Nécessite le **compte Premium du host** + authentification OAuth
- Les joueurs n'ont **rien à installer** — seul le host diffuse le son sur les enceintes PC/TV
- Contrôle programmatique play/pause/seek (utile pour ne révéler qu'un extrait précis, ex. à partir de `start_ms`)

### OAuth Spotify

- Flow **Authorization Code** côté backend
- Scopes : `streaming`, `user-read-playback-state`, `playlist-read-private`
- Refresh token stocké côté serveur
- Variables d'env : `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`

### Format d'une question blindtest

```json
{
  "type": "blindtest",
  "spotify_track_id": "3n3Ppam7vgaVa1iaRUc9Lp",
  "title": "Mr. Brightside",
  "artist": "The Killers",
  "cover_url": "...",
  "duration_ms": 222075,
  "start_ms": 45000,
  "answers": { "title": "Mr. Brightside", "artist": "The Killers" },
  "points": { "title": 1, "artist": 1 }
}
```

### Plan B / alternatives (si problème Premium ou besoin futur)

| Source | Note |
|---|---|
| iTunes / Apple Music preview API | extraits 30s, assez fiables, sans abonnement |
| Deezer API | previews 30s (en cours de restriction) |
| YouTube via `yt-dlp` | extraction audio de n'importe quel titre, flexible mais zone légale grise |
| Spotify `preview_url` | déprécié pour beaucoup de titres, non fiable |
