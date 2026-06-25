# Boucan

**Boucan** — quiz multijoueur en temps réel pour jouer entre amis à la maison
(buzzer, QCM façon Kahoot, blindtest Spotify). L'hôte mène la partie depuis un
PC/TV, les joueurs répondent depuis leur téléphone via le navigateur — pas d'app
à installer, pas de compte.

Voir [`cahier-des-charges.md`](./cahier-des-charges.md) pour la spécification complète.

## Fonctionnalités

- **Temps réel par WebSocket**, état **100 % en mémoire** (aucune base de données ;
  remis à zéro au redémarrage). Le serveur est l'unique source de vérité.
- **Console hôte privée** : choix du mode, préparation des questions à l'avance,
  scores éditables, exclusion de joueurs, salon de pré-partie avec QR de join.
- **Trois modes :**
  - **Buzzer** — arbitrage côté serveur (timestamp de réception, file ordonnée,
    idempotence), validation manuelle de l'hôte.
  - **QCM (style Kahoot)** — 4 choix, **timer serveur** (auto-révélation à
    l'expiration ou quand tout le monde a répondu), points **vitesse + bonus de
    série**, histogramme, **classement** ▲/▼, podium de fin.
  - **Blindtest Spotify** — lecture d'extraits via le Spotify Web Playback SDK
    (hôte Premium), décompte 3-2-1, minuterie de lecture **résistante au décalage
    d'horloge et aux pauses**, buzz pour donner titre/artiste, points titre/artiste
    **globaux**.
- **Bonus ×2** — n'importe quelle question/morceau peut être marqué « bonus » pour
  rapporter le double ; un badge ★ ×2 est visible de tous.
- **Packs prêts à jouer** — packs intégrés (QCM + Buzzer) pour lancer une partie
  sans rien écrire ; éditeur de packs (`/editor`) pour créer/importer/exporter les
  siens, persistés côté serveur.
- **Rejouer** en fin de partie (mêmes questions, scores remis à zéro).
- **Écran TV partagé** (`/tv/<code>`) : code + QR, question, buzzes/choix et
  scores — **jamais la bonne réponse** avant la révélation (filtrage par rôle).
- **Vue joueur mobile-first**, son + vibrations (buzz, décompte, bonne/mauvaise
  réponse) avec bouton couper-le-son.
- Reconnexion par `reconnect_token` + heartbeat `ping`/`pong`.

## Lancer (Docker — recommandé)

```bash
docker compose up --build
```

Sur le PC/TV, puis ouvre :

- `http://<ip-locale>:3200/host` — la **console de contrôle privée** (crée la partie)
- `http://<ip-locale>:3200/tv/<CODE>` — l'**écran TV partagé** (projeté / second écran)

Les joueurs rejoignent depuis leur téléphone (même WiFi) en scannant le QR ou via
`http://<ip-locale>:3200`. Le frontend se connecte automatiquement au backend sur le
même hôte, port **8200**.

> `<ip-locale>` = l'IP du PC sur le réseau (ex. `192.168.1.x`). `localhost` marche pour
> tester sur la même machine, mais les téléphones ont besoin de l'IP.

### Spotify (mode blindtest)

Le blindtest nécessite un compte **Spotify Premium** côté hôte et des identifiants
d'application Spotify. Copie `backend/.env.example` vers `backend/.env` et renseigne
`SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` / `SPOTIFY_REDIRECT_URI` /
`FRONTEND_URL`, puis connecte Spotify depuis la console hôte. Les autres modes
fonctionnent sans Spotify.

## Lancer en local (sans Docker)

Prérequis : [uv](https://docs.astral.sh/uv/) et Node 20+.

```bash
# Backend (port 8200)
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8200 --reload

# Frontend (port 3200) — dans un autre terminal
cd frontend && npm install && npm run dev
```

## Tests & qualité

```bash
# Backend — logique pure + intégration WebSocket
cd backend
uv run pytest
uv run ruff check .
uv run ruff format .

# Frontend — types + build
cd frontend
npx tsc --noEmit
npm run build
```

## Architecture

```
backend/                 FastAPI + WebSockets, état en mémoire
  game/engine.py         logique buzzer (arbitrage buzz, rounds, transitions)
  game/qcm.py            logique QCM (timer, scoring vitesse/série, reveal)
  game/blindtest.py      logique blindtest (timing pause-aware, points, bonus)
  game/builtin_packs.py  packs intégrés « prêts à jouer » (lecture seule)
  game/packs_store.py    persistance fichier des packs utilisateurs
  game/store.py          registre des sessions (dict code -> Session)
  game/spotify_client.py OAuth + recherche/playlists Spotify
  ws/manager.py          connexions host/joueurs/TV, broadcast/unicast
  routers/               sessions, packs, spotify (HTTP)
  main.py                app FastAPI, /health, WebSocket /ws, minuteries
frontend/                Next.js 15 + React 19 + Tailwind
  app/host/...           console privée (salon, éditeurs, contrôle en jeu)
  app/tv/...             écran TV partagé (lecture seule, sans réponse)
  app/play/...           vue joueur (buzzer / QCM / blindtest)
  app/editor/...         bibliothèque + éditeur de packs
  components/            Button, Equalizer, BonusChip/Toggle, Scoreboard, …
  lib/useGameSocket.ts   client WebSocket (reconnexion, heartbeat, horloge)
  lib/useSpotifyPlayer.ts  intégration Spotify Web Playback SDK (hôte)
  lib/sfx.ts             sons + vibrations
```

Les réponses correctes ne sont jamais envoyées aux joueurs **ni à la TV** avant la
révélation (cahier §16) : trois rôles WebSocket (`host`, `player`, `tv`), seul
l'hôte reçoit la réponse.
</content>
