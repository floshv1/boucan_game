"use client";

import { useEffect, useRef, useState } from "react";

import BonusChip from "@/components/BonusChip";
import Button from "@/components/Button";
import BuzzStrip from "@/components/BuzzStrip";
import Countdown from "@/components/Countdown";
import ElapsedTimer from "@/components/ElapsedTimer";
import Equalizer from "@/components/Equalizer";
import { CoverImage } from "@/components/MediaImage";
import * as sfx from "@/lib/sfx";
import { SpotifyPlayerControls } from "@/lib/useSpotifyPlayer";
import { GameSnapshot } from "@/lib/types";

interface Props {
  snapshot: GameSnapshot;
  action: (a: string, payload?: Record<string, unknown>) => void;
  spotify: SpotifyPlayerControls;
}

// Human labels for a track's œuvre type (mirrors backend ORIGIN_TYPES).
const ORIGIN_TYPE_LABELS: Record<string, string> = {
  jeu_video: "🎮 Jeu vidéo",
  film: "🎬 Film",
  serie: "📺 Série",
  anime: "🌸 Anime",
  autre: "🎵 Œuvre",
};

function originLabel(type?: string): string {
  return (type && ORIGIN_TYPE_LABELS[type]) || "🎵 Œuvre";
}

export default function BlindtestStage({ snapshot, action, spotify }: Props) {
  const bt = snapshot.blindtest;
  const playTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handledSeqRef = useRef<number>(-1);

  // Re-render ticker: animates countdown overlay and progress bar at 4 Hz.
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

  // Audio effect: keyed on bt.audioSeq (a server-side counter), not the track
  // URI. This lets identical directives re-fire (e.g. two replays in a row) and,
  // critically, distinguishes "start" (play snippet from start_ms, honouring the
  // countdown) from "resume" (continue from the buzz/pause point). Gated on
  // spotify.ready: a directive can arrive before the SDK device registers, so we
  // only mark a seq handled once we've actually acted on it (deps include ready).
  useEffect(() => {
    if (!spotify.ready) return;
    if (bt.audioSeq === handledSeqRef.current) return;
    handledSeqRef.current = bt.audioSeq;
    if (bt.audio === "pause") {
      spotify.pause();
    } else if (bt.audio === "resume") {
      spotify.resume();
      // Re-anchor the play window to the real resume moment (see mark_started).
      action("bt_started");
    } else if (bt.audio === "start" && bt.track) {
      const uri = bt.track.uri;
      const startMs = bt.track.start_ms;
      // Defer play until the server's segment start (covers the 3-2-1 countdown),
      // estimating server time from our clock + the measured offset.
      const delay = Math.max(0, bt.segStartedAt - (Date.now() + bt.clockOffset));
      if (playTimerRef.current) clearTimeout(playTimerRef.current);
      playTimerRef.current = setTimeout(() => {
        spotify.play(uri, startMs);
        // Tell the server playback actually started so the snippet isn't cut short
        // by SDK/countdown latency (the auto-pause re-anchors to this moment).
        action("bt_started");
      }, delay);
    }
    // spotify methods are stable callbacks — safe to exclude from deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bt.audioSeq, spotify.ready]);

  // Clear pending play timer on unmount.
  useEffect(() => () => { if (playTimerRef.current) clearTimeout(playTimerRef.current); }, []);

  // 3-2-1 countdown sound: tick each second, "go" when the music starts.
  const lastCdRef = useRef<number>(-1);
  useEffect(() => {
    const est = nowMs + bt.clockOffset;
    const counting = bt.playing && bt.segStartedAt > 0 && est < bt.segStartedAt;
    const sec = counting ? Math.ceil((bt.segStartedAt - est) / 1000) : 0;
    if (sec !== lastCdRef.current) {
      if (counting && sec > 0) sfx.tick();
      else if (!counting && lastCdRef.current > 0) sfx.go();
      lastCdRef.current = sec;
    }
  }, [nowMs, bt.clockOffset, bt.segStartedAt, bt.playing]);

  // GAME_END podium.
  if (bt.state === "GAME_END") {
    return (
      <div>
        <h2 className="font-display text-3xl">Partie terminée 🏆</h2>
        <ol className="mt-4 flex flex-col gap-2">
          {(bt.gameEnd?.podium ?? []).map((p) => (
            <li
              key={p.id}
              className="flex justify-between rounded-xl border border-panel2 bg-panel px-4 py-3"
            >
              <span className="font-display text-xl">
                {p.rank}. {p.pseudo}
              </span>
              <span className="font-display text-xl tabular-nums">{p.score}</span>
            </li>
          ))}
        </ol>
        <Button variant="primary" onClick={() => action("return_to_lobby")} className="mt-6 w-full">
          ⟲ Rejouer (retour au menu)
        </Button>
      </div>
    );
  }

  const buzzed =
    snapshot.buzz.state === "BUZZED" && !!snapshot.buzz.floor_player_id;
  const titleFound = !!bt.partial.titleBy;
  const artistFound = !!bt.partial.artistBy;
  const originFound = !!bt.partial.originBy;
  const hasOrigin = !!bt.track?.origin; // host sees the œuvre; players get bt.hasOrigin
  const applicableCount = 2 + (hasOrigin ? 1 : 0);
  const foundCount =
    (titleFound ? 1 : 0) + (artistFound ? 1 : 0) + (hasOrigin && originFound ? 1 : 0);
  // Some (but not all) applicable targets found → offer "Continuer" for the rest.
  const partialSomeFound = foundCount >= 1 && foundCount < applicableCount && bt.reveal === null;

  function pseudoById(id: string | null): string {
    if (!id) return "?";
    return snapshot.players.find((p) => p.id === id)?.pseudo ?? id;
  }

  // Estimated server clock (corrects for host/backend clock skew).
  const estServerNow = nowMs + bt.clockOffset;

  // Countdown overlay: only while the segment clock is running but not yet reached.
  const countingDown =
    bt.playing && bt.segStartedAt > 0 && estServerNow < bt.segStartedAt;
  const countdownSecs = countingDown
    ? Math.ceil((bt.segStartedAt - estServerNow) / 1000)
    : 0;

  // Progress bar: pause-aware (freezes when !playing) and clock-skew-safe.
  const hasCap = bt.maxPlayMs > 0;
  const elapsedMs = bt.playing
    ? bt.playedMs + Math.max(0, estServerNow - bt.segStartedAt)
    : bt.playedMs;
  const progress = hasCap ? Math.min(1, elapsedMs / bt.maxPlayMs) : 0;
  const showProgress = hasCap && !!bt.track && !countingDown;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 font-display text-2xl">
          Morceau {bt.index + 1}/{bt.total}
          {bt.bonus && <BonusChip />}
        </h2>
        <span
          className={`rounded-full px-3 py-1 font-mono text-xs ${
            spotify.error
              ? "bg-buzz/20 text-buzz"
              : spotify.ready
              ? "bg-volt/20 text-volt"
              : "bg-panel2 text-muted"
          }`}
        >
          {spotify.error
            ? spotify.error
            : spotify.ready
            ? "lecteur prêt"
            : "lecteur…"}
        </span>
      </div>

      {/* Now playing — countdown overlay or host-only track info */}
      {bt.track && (
        countingDown ? (
          <div className="mt-4 flex flex-col items-center justify-center gap-3 rounded-xl border border-panel2 bg-ink/40 px-4 py-6">
            <Equalizer bars={7} className="h-8" />
            <span
              key={countdownSecs}
              className="countdown-pop font-display text-7xl text-volt tabular-nums"
            >
              {countdownSecs}
            </span>
          </div>
        ) : (
          <div className="mt-4 flex items-center gap-4 rounded-xl border border-panel2 bg-ink/40 px-4 py-3">
            {bt.track.cover_url && (
              <CoverImage src={bt.track.cover_url} size={56} className="h-14 w-14 shrink-0 rounded-lg" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate font-display text-lg">{bt.track.title}</p>
              <p className="truncate font-mono text-sm text-muted">{bt.track.artist}</p>
              {bt.track.origin && (
                <p className="mt-0.5 truncate font-mono text-xs text-volt">
                  {originLabel(bt.track.origin_type)} · {bt.track.origin}
                </p>
              )}
            </div>
          </div>
        )
      )}

      {/* Progress bar */}
      {showProgress && (
        <div className="mt-3 flex items-center gap-3">
          <Equalizer bars={4} className="h-4" animated={bt.playing} />
          <div className="h-2 flex-1 rounded bg-panel2">
            <div
              className="h-2 rounded bg-volt transition-[width] duration-200 ease-linear"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Manual audio controls: play/pause toggle + restart-from-start */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          variant="primary"
          onClick={() => {
            if (!bt.track) return;
            if (bt.playing) {
              action("pause_bt");
              spotify.pause();
            } else {
              action("resume_bt");
              spotify.resume();
            }
          }}
          disabled={!bt.track}
        >
          {bt.playing ? "⏸ Pause" : "▶ Lecture"}
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            if (!bt.track) return;
            action("replay_bt");
            spotify.play(bt.track.uri, bt.track.start_ms);
          }}
          disabled={!bt.track}
        >
          ⟲ Rejouer
        </Button>
        <label className="ml-auto flex items-center gap-2 font-mono text-xs text-muted">
          Volume
          <input
            type="range" min={0} max={1} step={0.05}
            value={spotify.volume}
            onChange={(e) => spotify.setVolume(Number(e.target.value))}
            className="w-32"
          />
        </label>
      </div>

      {/* Buzz strip */}
      <div className="mt-5">
        <BuzzStrip
          queue={snapshot.buzz.queue}
          floorPlayerId={snapshot.buzz.floor_player_id}
        />
      </div>

      {/* Found so far */}
      {(titleFound || artistFound || originFound) && (
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 rounded-xl border border-panel2 bg-ink/20 px-4 py-2 font-mono text-sm text-muted">
          {titleFound && (
            <span>
              Titre trouvé par{" "}
              <span className="text-volt">{pseudoById(bt.partial.titleBy)}</span>
            </span>
          )}
          {artistFound && (
            <span>
              Artiste trouvé par{" "}
              <span className="text-volt">{pseudoById(bt.partial.artistBy)}</span>
            </span>
          )}
          {originFound && (
            <span>
              Œuvre trouvée par{" "}
              <span className="text-volt">{pseudoById(bt.partial.originBy)}</span>
            </span>
          )}
        </div>
      )}

      {/* Post-buzz answer countdown for the floor-holder (count-up when no limit) */}
      {buzzed && (
        <div className="mt-3 flex items-center gap-2 font-mono text-sm text-buzz">
          ⏱ Réponse :
          {(snapshot.buzz.answer_ends_at ?? 0) > 0 ? (
            <Countdown endsAt={snapshot.buzz.answer_ends_at ?? 0} offsetMs={bt.clockOffset} />
          ) : (
            <ElapsedTimer offsetMs={bt.clockOffset} />
          )}
        </div>
      )}

      {/* Post-music grace: auto-reveal countdown when nobody holds the floor */}
      {!buzzed && bt.revealEndsAt > 0 && bt.state === "BUZZER_OPEN" && (
        <div className="mt-3 flex items-center gap-2 font-mono text-sm text-muted">
          ⏱ Révélation auto dans :
          <Countdown endsAt={bt.revealEndsAt} offsetMs={bt.clockOffset} />
        </div>
      )}

      {/* Validation buttons */}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => action("validate_bt", { title: true })} disabled={!buzzed}>
          ✓ Titre
        </Button>
        <Button variant="primary" onClick={() => action("validate_bt", { artist: true })} disabled={!buzzed}>
          ✓ Artiste
        </Button>
        <Button variant="primary" onClick={() => action("validate_bt", { title: true, artist: true })} disabled={!buzzed}>
          ✓ Les deux
        </Button>
        {hasOrigin && (
          <Button
            variant="primary"
            onClick={() => action("validate_bt", { origin: true })}
            disabled={!buzzed}
          >
            ✓ Œuvre
          </Button>
        )}
        <Button variant="danger" onClick={() => action("invalidate")} disabled={!buzzed}>
          ✗ Faux
        </Button>
      </div>

      {/* Partial controls */}
      {partialSomeFound && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary" onClick={() => action("continue_bt")}>
            ▶ Continuer (points restants)
          </Button>
          <Button variant="ghost" onClick={() => action("reveal")}>
            Révéler
          </Button>
        </div>
      )}

      {/* Reveal banner */}
      {bt.reveal && (
        <div className="mt-4 flex items-center gap-4 rounded-xl border border-volt/40 bg-volt/10 px-4 py-3">
          {bt.reveal.cover_url && (
            <CoverImage src={bt.reveal.cover_url} size={48} className="h-12 w-12 shrink-0 rounded-lg" />
          )}
          <div className="min-w-0">
            <p className="font-display text-lg text-volt">
              ✓ {bt.reveal.title} — {bt.reveal.artist}
            </p>
            {bt.reveal.origin && (
              <p className="truncate font-mono text-sm text-cream">
                {originLabel(bt.reveal.origin_type)} · {bt.reveal.origin}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Scoreboard (SCOREBOARD state) */}
      {bt.state === "SCOREBOARD" && bt.scoreboard.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 font-mono text-xs uppercase tracking-widest text-muted">
            Classement
          </p>
          <ol className="flex flex-col gap-1.5">
            {bt.scoreboard.map((row) => (
              <li
                key={row.id}
                className="flex items-center gap-3 rounded-xl border border-panel2 bg-panel px-3 py-2"
              >
                <span className="w-6 font-display text-lg text-muted">{row.rank}</span>
                <span className="flex-1 truncate">{row.pseudo}</span>
                <span className="font-display text-lg tabular-nums">{row.score}</span>
                {row.delta !== 0 && (
                  <span
                    className={`font-mono text-xs ${
                      row.delta > 0 ? "text-volt" : "text-buzz"
                    }`}
                  >
                    {row.delta > 0 ? `▲ +${row.delta}` : `▼ ${row.delta}`}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Always-visible flow control — one state-driven button so the
          reveal → scoreboard → next-track progression is never ambiguous. */}
      <div className="mt-4 flex flex-wrap gap-2">
        {/* Reveal: available while the round is live and not already revealed
            (the partial block has its own Révéler when one field is found). */}
        {!partialSomeFound &&
          bt.state !== "REVEAL" &&
          bt.state !== "SCOREBOARD" &&
          bt.reveal === null && (
            <Button variant="ghost" onClick={() => action("reveal")}>
              Révéler
            </Button>
          )}
        {bt.state === "REVEAL" && (
          <Button variant="primary" onClick={() => action("next")}>
            Classement →
          </Button>
        )}
        {bt.state === "SCOREBOARD" && (
          <Button variant="primary" onClick={() => action("next")}>
            Morceau suivant →
          </Button>
        )}
      </div>
    </div>
  );
}
