"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import BlindtestStage from "@/components/BlindtestStage";
import BuzzStrip from "@/components/BuzzStrip";
import Countdown from "@/components/Countdown";
import JoinCard from "@/components/JoinCard";
import BonusChip from "@/components/BonusChip";
import Button from "@/components/Button";
import MuteToggle from "@/components/MuteToggle";
import PackPicker from "@/components/PackPicker";
import Scoreboard from "@/components/Scoreboard";
import SpotifyConnect from "@/components/SpotifyConnect";
import { useGameSocket } from "@/lib/useGameSocket";
import { useNow } from "@/lib/useNow";
import { useSpotifyPlayer } from "@/lib/useSpotifyPlayer";
import { BlindtestTrackDraft, BuzzerRowDraft, QcmRoundDraft } from "@/lib/types";

export default function HostConsole() {
  const code = String(useParams().code ?? "").toUpperCase();
  const [secret, setSecret] = useState<string | null | undefined>(undefined);
  const [joinUrl, setJoinUrl] = useState("");
  const [tvUrl, setTvUrl] = useState("");
  const [copied, setCopied] = useState(false);

  // Mode toggle state (3 modes now).
  const [mode, setMode] = useState<"buzzer" | "qcm" | "blindtest">("buzzer");

  // Selected pack content per mode (questions merged from the chosen packs).
  // Questions are authored in the editor; the host only picks packs, and we
  // shuffle the merged list when the game starts.
  const [buzzerItems, setBuzzerItems] = useState<BuzzerRowDraft[]>([]);
  const [qcmItems, setQcmItems] = useState<QcmRoundDraft[]>([]);
  const [btItems, setBtItems] = useState<BlindtestTrackDraft[]>([]);

  // How many questions/tracks to draw from the selected packs each game. Fixed
  // default, capped to the available total when starting (see pickN).
  const DEFAULT_DRAW = 10;
  const [drawCount, setDrawCount] = useState(DEFAULT_DRAW);

  // Per-game settings not carried by individual questions.
  const [shuffleChoices, setShuffleChoices] = useState(false);
  // Buzzer round time limit in seconds (0 = no limit → auto-reveal disabled).
  const [buzzLimitS, setBuzzLimitS] = useState(20);
  const [btSettings, setBtSettings] = useState({
    maxPlayS: 30,
    randomStart: false,
    countdown: true,
    pointsTitle: 1,
    pointsArtist: 1,
  });

  useEffect(() => {
    setSecret(localStorage.getItem(`quiz:host:${code}`));
    setJoinUrl(`${window.location.origin}/play?code=${code}`);
    setTvUrl(`${window.location.origin}/tv/${code}`);
  }, [code]);

  const { snapshot, send } = useGameSocket({
    code,
    role: "host",
    hostSecret: secret ?? "",
    enabled: !!secret,
  });

  // Call the Spotify player hook unconditionally at the top level (React hooks rule).
  // Enabled whenever blindtest mode is active (either selected in UI or live in game).
  const isBlindtest = mode === "blindtest" || snapshot.blindtest.mode === "blindtest";
  // Wait for the host secret before connecting: the token endpoint is gated on it.
  const spotify = useSpotifyPlayer(isBlindtest && !!secret, secret ?? "");
  const now = useNow();

  if (secret === null) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 text-center">
        <h1 className="font-display text-4xl">Hôte introuvable</h1>
        <p className="mt-4 text-cream/80">
          Cet appareil n&apos;a pas créé la partie <b>{code}</b>. Ouvre la console depuis l&apos;écran qui l&apos;a
          lancée.
        </p>
        <Link href="/host" className="mt-8 font-display text-xl text-buzz">
          Créer une nouvelle partie →
        </Link>
      </main>
    );
  }

  const { round, players, buzz, reveal } = snapshot;
  const state = round.state;
  const floorOpen = state === "BUZZED" && !round.revealed && round.floor_player_id;
  const floorPseudo = players.find((p) => p.id === round.floor_player_id)?.pseudo;

  // Determine which mode is actively running on the server.
  const activeMode =
    snapshot.blindtest.mode === "blindtest"
      ? "blindtest"
      : snapshot.qcm.mode === "qcm"
      ? "qcm"
      : "buzzer";

  // showConfig: true while we're in the lobby for the active mode.
  const showConfig =
    activeMode === "blindtest"
      ? snapshot.blindtest.state === "LOBBY"
      : activeMode === "qcm"
      ? snapshot.qcm.state === "LOBBY"
      : round.state === "LOBBY";

  const action = (a: string, payload: Record<string, unknown> = {}) => send("host_action", { action: a, ...payload });

  // Fisher–Yates: a fresh random order on every start, so the same packs play
  // differently each game.
  function shuffled<T>(arr: T[]): T[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // Shuffle, then keep at most `drawCount` items (clamped to what's available).
  function pickN<T>(arr: T[]): T[] {
    const n = Math.max(1, Math.min(drawCount, arr.length));
    return shuffled(arr).slice(0, n);
  }

  // Effective number drawn for a given pool size, for button labels.
  const effectiveCount = (total: number) => Math.max(1, Math.min(drawCount, total));

  function startGame() {
    if (buzzerItems.length === 0) return;
    const prepared = pickN(buzzerItems).map((r) => ({
      question_text: (r.question ?? "").trim() || null,
      answer: (r.answer ?? "").trim() || null,
      points: r.points || 1,
      bonus: !!r.bonus,
      image: r.image ?? null,
    }));
    action("set_rounds", { rounds: prepared, buzz_limit_s: buzzLimitS });
    action("start_game");
  }

  function startQcm() {
    if (qcmItems.length === 0) return;
    action("set_qcm_rounds", {
      rounds: pickN(qcmItems),
      shuffle_questions: false, // already shuffled client-side
      shuffle_choices: shuffleChoices,
    });
    action("start_qcm");
  }

  function startBlindtest() {
    if (btItems.length === 0) return;
    action("set_blindtest_tracks", {
      tracks: pickN(btItems),
      max_play_s: btSettings.maxPlayS,
      random_start: btSettings.randomStart,
      countdown: btSettings.countdown,
      points_title: btSettings.pointsTitle,
      points_artist: btSettings.pointsArtist,
    });
    action("start_blindtest");
  }

  function copyJoin() {
    navigator.clipboard?.writeText(joinUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const preparedCount = buzzerItems.length;
  const qcmCount = qcmItems.length;

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-5">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-panel2 pb-5">
        <JoinCard code={code} joinUrl={joinUrl} size={92} />
        <div className="text-right">
          <button onClick={copyJoin} className="block font-mono text-sm text-cream/80 underline decoration-muted">
            {copied ? "Lien joueur copié ✓" : "Copier le lien joueur"}
          </button>
          <a
            href={tvUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-1 block font-mono text-sm text-volt underline decoration-volt/50"
          >
            Ouvrir l&apos;écran TV ↗
          </a>
          <p className="mt-2 flex items-center justify-end gap-2 font-mono text-xs text-muted">
            <span className={`h-2 w-2 rounded-full ${snapshot.connected ? "bg-volt" : "bg-buzz"}`} />
            {snapshot.connected ? "connecté" : "reconnexion…"} · {players.length} joueur
            {players.length > 1 ? "s" : ""}
            <MuteToggle className="ml-1" />
          </p>
        </div>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        {/* Round panel */}
        <section className="rounded-2xl border border-panel2 bg-panel/60 p-5">
          {showConfig ? (
            <div>
              <h2 className="font-display text-3xl">Préparer la partie</h2>
              <p className="mt-1 text-sm text-muted">
                Choisis un ou plusieurs packs — les questions sont tirées au hasard à chaque partie. Crée ou modifie
                tes packs dans l&apos;éditeur.
              </p>

              {/* Mode toggle — 3 buttons, even width + comfortable tap targets */}
              <div className="mb-4 mt-4 grid grid-cols-3 gap-2">
                {(["buzzer", "qcm", "blindtest"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`min-h-[44px] rounded-lg px-2 py-2 font-display text-base sm:text-lg ${
                      mode === m ? "bg-volt text-ink" : "border border-panel2 text-cream hover:border-muted"
                    }`}
                  >
                    {m === "buzzer" ? "Buzzer" : m === "qcm" ? "QCM" : "Blindtest"}
                  </button>
                ))}
              </div>

              {mode === "buzzer" && (
                <div className="flex flex-col gap-3">
                  <PackPicker mode="buzzer" onItemsChange={(items) => setBuzzerItems(items as BuzzerRowDraft[])} />

                  {preparedCount > 0 && (
                    <label className="flex items-center gap-2 rounded-xl border border-panel2 bg-ink/30 p-3 font-mono text-xs text-muted">
                      Nombre de questions
                      <input
                        type="number"
                        min={1}
                        max={preparedCount}
                        value={Math.min(drawCount, preparedCount)}
                        onChange={(e) => setDrawCount(Math.max(1, Number.parseInt(e.target.value, 10) || 1))}
                        className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                      />
                      <span className="text-muted/70">sur {preparedCount} disponible{preparedCount > 1 ? "s" : ""}</span>
                    </label>
                  )}

                  <label className="flex items-center gap-2 rounded-xl border border-panel2 bg-ink/30 p-3 font-mono text-xs text-muted">
                    Temps limite (s)
                    <input
                      type="number"
                      min={0}
                      value={buzzLimitS}
                      onChange={(e) => setBuzzLimitS(Math.max(0, Number.parseInt(e.target.value, 10) || 0))}
                      className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                    />
                    <span className="text-muted/70">0 = illimité · révélation auto sinon</span>
                  </label>

                  <Button variant="accent" size="lg" onClick={startGame} disabled={preparedCount === 0} className="mt-2 w-full">
                    Démarrer ({effectiveCount(preparedCount)} round{effectiveCount(preparedCount) > 1 ? "s" : ""})
                  </Button>

                  <Button variant="ghost" onClick={() => action("open_buzzer", { buzz_limit_s: buzzLimitS })}>
                    Buzzer immédiat (sans texte)
                  </Button>
                </div>
              )}

              {mode === "qcm" && (
                <div className="flex flex-col gap-3">
                  <PackPicker mode="qcm" onItemsChange={(items) => setQcmItems(items as QcmRoundDraft[])} />
                  {qcmCount > 0 && (
                    <label className="flex items-center gap-2 rounded-xl border border-panel2 bg-ink/30 p-3 font-mono text-xs text-muted">
                      Nombre de questions
                      <input
                        type="number"
                        min={1}
                        max={qcmCount}
                        value={Math.min(drawCount, qcmCount)}
                        onChange={(e) => setDrawCount(Math.max(1, Number.parseInt(e.target.value, 10) || 1))}
                        className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                      />
                      <span className="text-muted/70">sur {qcmCount} disponible{qcmCount > 1 ? "s" : ""}</span>
                    </label>
                  )}
                  <label className="flex items-center gap-2 rounded-xl border border-panel2 bg-ink/30 p-3 font-mono text-xs text-muted">
                    <input type="checkbox" checked={shuffleChoices} onChange={(e) => setShuffleChoices(e.target.checked)} />
                    Mélanger l&apos;ordre des réponses
                  </label>
                  <Button variant="accent" size="lg" onClick={startQcm} disabled={qcmCount === 0} className="mt-2 w-full">
                    Démarrer le QCM ({effectiveCount(qcmCount)} question{effectiveCount(qcmCount) > 1 ? "s" : ""})
                  </Button>
                </div>
              )}

              {mode === "blindtest" && (
                <div className="flex flex-col gap-4">
                  <SpotifyConnect />
                  <PackPicker mode="blindtest" onItemsChange={(items) => setBtItems(items as BlindtestTrackDraft[])} />
                  {btItems.length > 0 && (
                    <label className="flex items-center gap-2 rounded-xl border border-panel2 bg-ink/30 p-3 font-mono text-xs text-muted">
                      Nombre de musiques
                      <input
                        type="number"
                        min={1}
                        max={btItems.length}
                        value={Math.min(drawCount, btItems.length)}
                        onChange={(e) => setDrawCount(Math.max(1, Number.parseInt(e.target.value, 10) || 1))}
                        className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                      />
                      <span className="text-muted/70">sur {btItems.length} disponible{btItems.length > 1 ? "s" : ""}</span>
                    </label>
                  )}
                  <div className="flex flex-wrap items-center gap-4 rounded-xl border border-panel2 bg-ink/20 px-4 py-3 font-mono text-xs text-muted">
                    <label className="flex items-center gap-2">
                      Temps max (s)
                      <input
                        type="number"
                        min={0}
                        value={btSettings.maxPlayS}
                        onChange={(e) => setBtSettings((s) => ({ ...s, maxPlayS: Number.parseInt(e.target.value, 10) || 0 }))}
                        className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                      />
                    </label>
                    <label className="flex items-center gap-2">
                      Pts titre
                      <input
                        type="number"
                        min={0}
                        value={btSettings.pointsTitle}
                        onChange={(e) => setBtSettings((s) => ({ ...s, pointsTitle: Number.parseInt(e.target.value, 10) || 0 }))}
                        className="w-14 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                      />
                    </label>
                    <label className="flex items-center gap-2">
                      Pts artiste
                      <input
                        type="number"
                        min={0}
                        value={btSettings.pointsArtist}
                        onChange={(e) => setBtSettings((s) => ({ ...s, pointsArtist: Number.parseInt(e.target.value, 10) || 0 }))}
                        className="w-14 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                      />
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={btSettings.randomStart}
                        onChange={(e) => setBtSettings((s) => ({ ...s, randomStart: e.target.checked }))}
                      />
                      Départ aléatoire
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={btSettings.countdown}
                        onChange={(e) => setBtSettings((s) => ({ ...s, countdown: e.target.checked }))}
                      />
                      Décompte 3-2-1
                    </label>
                    <span className="text-muted/70">Bonus ★ = ×2 · 0 s = pas de limite</span>
                  </div>
                  <Button variant="accent" size="lg" onClick={startBlindtest} disabled={btItems.length === 0} className="mt-2 w-full">
                    Démarrer le blindtest ({effectiveCount(btItems.length)} morceau{effectiveCount(btItems.length) > 1 ? "x" : ""})
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div>
              {activeMode === "blindtest" ? (
                <BlindtestStage snapshot={snapshot} action={action} spotify={spotify} />
              ) : activeMode === "qcm" ? (
                <div>
                  {snapshot.qcm.state === "GAME_END" ? (
                    <div>
                      <h2 className="font-display text-3xl">Partie terminée 🏆</h2>
                      <ol className="mt-4 flex flex-col gap-2">
                        {(snapshot.qcm.gameEnd?.podium ?? []).map((p) => (
                          <li key={p.id} className="flex justify-between rounded-xl border border-panel2 bg-panel px-4 py-3">
                            <span className="font-display text-xl">{p.rank}. {p.pseudo}</span>
                            <span className="font-display text-xl tabular-nums">{p.score}</span>
                          </li>
                        ))}
                      </ol>
                      <Button variant="primary" onClick={() => action("return_to_lobby")} className="mt-6 w-full">
                        ⟲ Rejouer (retour au menu)
                      </Button>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-center justify-between gap-3">
                        <h2 className="flex items-center gap-2 font-display text-2xl">
                          Question {snapshot.qcm.index + 1}/{snapshot.qcm.total}
                          {snapshot.qcm.question?.bonus && <BonusChip />}
                        </h2>
                        {snapshot.qcm.state === "QUESTION_ACTIVE" && snapshot.qcm.question && (
                          <span className="font-mono text-sm text-muted">
                            {snapshot.qcm.progress.answered}/{snapshot.qcm.progress.total} ont répondu
                          </span>
                        )}
                      </div>
                      {snapshot.qcm.state === "QUESTION_ACTIVE" && snapshot.qcm.question && (
                        <Countdown
                          endsAt={snapshot.qcm.question.ends_at}
                          offsetMs={snapshot.qcm.clockOffset}
                          durationMs={snapshot.qcm.question.time_limit * 1000}
                          className="mt-3"
                        />
                      )}
                      {snapshot.qcm.question && <p className="mt-3 text-xl">{snapshot.qcm.question.question}</p>}
                      <ul className="mt-4 grid grid-cols-2 gap-2">
                        {(snapshot.qcm.question?.choices ?? []).map((c, i) => {
                          const correct = snapshot.qcm.question?.correct;
                          const revealedCorrect = snapshot.qcm.reveal?.correct;
                          const isRight = i === correct || i === revealedCorrect;
                          return (
                            <li
                              key={i}
                              className={`rounded-xl border px-3 py-3 ${isRight ? "border-volt bg-volt/15 text-volt" : "border-panel2"}`}
                            >
                              {c}
                              {snapshot.qcm.reveal && (
                                <span className="ml-2 font-mono text-xs text-muted">{snapshot.qcm.reveal.distribution[i]}</span>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                      <div className="mt-5 flex flex-wrap gap-2">
                        {snapshot.qcm.state === "QUESTION_ACTIVE" && (
                          <>
                            <Button variant="primary" onClick={() => action("reveal")}>
                              Révéler maintenant
                            </Button>
                            <Button variant="ghost" onClick={() => action("skip")}>
                              Passer (0 pt)
                            </Button>
                          </>
                        )}
                        {snapshot.qcm.state === "REVEAL" && (
                          <Button variant="primary" onClick={() => action("next")}>
                            Classement →
                          </Button>
                        )}
                        {snapshot.qcm.state === "SCOREBOARD" && (
                          <Button variant="primary" onClick={() => action("next")}>
                            Question suivante →
                          </Button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : state === "GAME_END" ? (
                <div>
                  <h2 className="font-display text-3xl">Partie terminée 🏆</h2>
                  <ol className="mt-4 flex flex-col gap-2">
                    {[...players].sort((a, b) => a.rank - b.rank).slice(0, 5).map((p) => (
                      <li key={p.id} className="flex justify-between rounded-xl border border-panel2 bg-panel px-4 py-3">
                        <span className="font-display text-xl">{p.rank}. {p.pseudo}</span>
                        <span className="font-display text-xl tabular-nums">{p.score}</span>
                      </li>
                    ))}
                  </ol>
                  <Button variant="primary" onClick={() => action("return_to_lobby")} className="mt-6 w-full">
                    ⟲ Rejouer (retour au menu)
                  </Button>
                </div>
              ) : (
                <div>
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="flex items-center gap-2 font-display text-3xl">
                      {state === "BUZZED" ? (
                        <>
                          <span className="text-volt">{floorPseudo ?? "Quelqu'un"}</span> a la main
                        </>
                      ) : (
                        "Buzzer ouvert"
                      )}
                      {round.bonus && <BonusChip />}
                    </h2>
                    <span className="font-mono text-sm text-muted">
                      {round.round_total > 0 && `Round ${round.round_index + 1}/${round.round_total} · `}
                      {round.points} pt
                    </span>
                  </div>

                  {round.question_text && <p className="mt-3 text-xl">{round.question_text}</p>}
                  {round.answer && <p className="mt-2 font-mono text-sm text-volt">réponse : {round.answer}</p>}

                  {state === "BUZZER_OPEN" &&
                    !round.revealed &&
                    (round.buzz_ends_at ?? 0) > 0 &&
                    (round.buzz_open_at ?? 0) <= now + (round.clockOffset ?? 0) && (
                      <Countdown
                        endsAt={round.buzz_ends_at ?? 0}
                        offsetMs={round.clockOffset}
                        durationMs={(round.buzz_ends_at ?? 0) - (round.buzz_open_at ?? 0)}
                        className="mt-3"
                      />
                    )}

                  <div className="mt-5">
                    <BuzzStrip queue={buzz.queue} floorPlayerId={round.floor_player_id} />
                  </div>

                  {reveal && (
                    <p className="mt-4 rounded-xl border border-volt/40 bg-volt/10 px-4 py-3">
                      Réponse révélée{reveal.answer ? ` : ${reveal.answer}` : ""}
                    </p>
                  )}

                  {/* Judge the player who has the floor (only while someone holds it) */}
                  {floorOpen && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      <Button variant="primary" onClick={() => action("validate")}>
                        ✓ Valider {floorPseudo ? `(${floorPseudo})` : ""}
                      </Button>
                      <Button variant="danger" onClick={() => action("invalidate")}>
                        ✗ Invalider
                      </Button>
                    </div>
                  )}

                  {/* Round flow */}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {!round.revealed ? (
                      <Button variant="primary" onClick={() => action("reveal")}>
                        Révéler la réponse
                      </Button>
                    ) : (
                      <Button variant="primary" onClick={() => action("next")}>
                        Suivant →
                      </Button>
                    )}
                    {/* Once a round is revealed (someone found, or the host gave up) the
                        buzzer must not reopen — only "Suivant" advances. */}
                    {!round.revealed && (
                      <Button variant="ghost" onClick={() => action("reset_buzzer")}>
                        Rouvrir le buzzer
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Right column: a join-focused "Salon" while preparing, the scoreboard once live */}
        <section className="rounded-2xl border border-panel2 bg-panel/60 p-5">
          {showConfig ? (
            <div className="flex flex-col gap-5">
              <div>
                <h2 className="font-display text-3xl">Salon</h2>
                <p className="mt-1 text-sm text-muted">Scanne le QR ou tape le code pour rejoindre.</p>
              </div>
              <div className="flex justify-center rounded-xl border border-panel2 bg-ink/30 p-4">
                <JoinCard code={code} joinUrl={joinUrl} size={160} />
              </div>
              <div>
                <p className="mb-2 font-mono text-xs uppercase tracking-widest text-muted">
                  {players.length} joueur{players.length > 1 ? "s" : ""} dans le salon
                </p>
                {players.length === 0 ? (
                  <p className="font-mono text-sm text-muted">En attente des joueurs…</p>
                ) : (
                  <ul className="flex flex-wrap gap-2">
                    {players.map((p) => (
                      <li
                        key={p.id}
                        className={`rounded-full border px-3 py-1.5 text-sm ${
                          p.connected ? "border-volt/40 bg-volt/10 text-cream" : "border-panel2 text-muted opacity-60"
                        }`}
                      >
                        {p.pseudo}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <>
              <h2 className="mb-4 font-display text-3xl">Scores</h2>
              <Scoreboard
                players={players}
                highlightId={round.floor_player_id ?? undefined}
                onAdjust={(id, delta) => action("adjust_score", { player_id: id, delta })}
                onKick={(id) => action("kick", { player_id: id })}
              />
            </>
          )}
        </section>
      </div>
    </main>
  );
}
