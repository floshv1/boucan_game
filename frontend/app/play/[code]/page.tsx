"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import BlindtestTimerBar from "@/components/BlindtestTimerBar";
import BonusChip from "@/components/BonusChip";
import Buzzer from "@/components/Buzzer";
import Countdown from "@/components/Countdown";
import ElapsedTimer from "@/components/ElapsedTimer";
import { CoverImage, PromptImage } from "@/components/MediaImage";
import QcmChoices from "@/components/QcmChoices";
import ReadingBadge from "@/components/ReadingBadge";
import Scoreboard from "@/components/Scoreboard";
import ScoreFooter from "@/components/ScoreFooter";
import ScreenHeader from "@/components/ScreenHeader";
import * as sfx from "@/lib/sfx";
import { useGameSocket } from "@/lib/useGameSocket";
import { useNow } from "@/lib/useNow";

export default function PlayerView() {
  const code = String(useParams().code ?? "").toUpperCase();
  const router = useRouter();
  const [pseudo, setPseudo] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setPseudo(localStorage.getItem(`quiz:pseudo:${code}`));
  }, [code]);

  useEffect(() => {
    if (pseudo === null) router.replace(`/play?code=${code}`);
  }, [pseudo, code, router]);

  const { snapshot, send } = useGameSocket({
    code,
    role: "player",
    pseudo: pseudo ?? "",
    enabled: !!pseudo,
  });

  // Reveal sound cues: a win chimes for anyone who scored; a miss only buzzes
  // the player who actually answered (QCM) so spectators aren't nagged.
  const phaseRef = useRef<string>("");
  useEffect(() => {
    const s = snapshot;
    const yid = s.you.id ?? "";
    let phase = "";
    let cue: "correct" | "wrong" | null = null;
    if (s.qcm.mode === "qcm") {
      if (s.qcm.state === "REVEAL" && s.qcm.reveal) {
        phase = "qcm-reveal";
        const won = s.qcm.myChoice !== null && s.qcm.myChoice === s.qcm.reveal.correct;
        cue = won ? "correct" : s.qcm.myChoice !== null ? "wrong" : null;
      } else phase = `qcm-${s.qcm.state}`;
    } else if (s.blindtest.mode === "blindtest") {
      if (s.blindtest.state === "REVEAL" && s.blindtest.reveal) {
        phase = "bt-reveal";
        cue = (s.blindtest.reveal.deltas[yid] ?? 0) > 0 ? "correct" : null;
      } else phase = `bt-${s.blindtest.state}`;
    } else {
      if (s.round.revealed) {
        phase = "bz-reveal";
        cue = s.reveal?.correct_player_id === yid ? "correct" : null;
      } else phase = `bz-${s.round.state}`;
    }
    if (phase !== phaseRef.current) {
      phaseRef.current = phase;
      if (cue === "correct") sfx.correct();
      else if (cue === "wrong") sfx.wrong();
    }
  }, [snapshot]);

  // Stable handlers so the memoised QcmChoices / Buzzer skip re-renders when the
  // snapshot changes for unrelated reasons (`send` is already a stable callback).
  const submitAnswer = useCallback((i: number) => send("answer_submit", { choice: i }), [send]);
  const doBuzz = useCallback(() => { sfx.buzz(); send("buzz"); }, [send]);
  const noop = useCallback(() => {}, []);

  const now = useNow();

  if (!pseudo) return null;

  const { round, players, buzz, reveal, you, error } = snapshot;
  const me = players.find((p) => p.id === you.id);
  // Standings shown to players on scoreboard / game-end screens (sorted by rank).
  const ranking = [...players].sort((a, b) => a.rank - b.rank);

  if (error?.code === "kicked") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <h1 className="font-display text-5xl text-buzz">Exclu</h1>
        <p className="mt-4 text-cream/80">L&apos;hôte t&apos;a retiré de la partie.</p>
        <Link href="/play" className="mt-8 font-display text-xl text-cream underline">
          Rejoindre à nouveau
        </Link>
      </main>
    );
  }

  const q = snapshot.qcm;
  if (q.mode === "qcm") {
    const reveal = q.reveal;
    const won = reveal && q.myChoice !== null && q.myChoice === reveal.correct;
    return (
      <main className="flex min-h-screen flex-col px-5 py-5">
        <ScreenHeader code={code} pseudo={me?.pseudo ?? pseudo} connected={snapshot.connected} />

        {q.state === "QUESTION_ACTIVE" && q.question ? (
          (() => {
            const reading = (q.question.choices_at ?? 0) > now + q.clockOffset;
            const readSecs = Math.ceil(((q.question.choices_at ?? 0) - (now + q.clockOffset)) / 1000);
            return (
              <>
                <div className="mt-4 flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 font-mono text-xs text-muted">
                    Question {q.index + 1}/{q.total}
                    {q.question.bonus && <BonusChip />}
                  </span>
                </div>
                {!reading && (
                  <Countdown
                    endsAt={q.question.ends_at}
                    offsetMs={q.clockOffset}
                    durationMs={q.question.time_limit * 1000}
                    className="mt-2 text-muted"
                  />
                )}
                <p className="mt-3 text-center text-lg">{q.question.question}</p>
                {q.question.image && <PromptImage src={q.question.image} className="mx-auto mt-3 max-h-40 rounded-lg" />}
                {reading ? (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6">
                    <ReadingBadge secondsLeft={readSecs} />
                    <p className="font-mono text-sm text-muted">Lis bien la question…</p>
                  </div>
                ) : (
                  <>
                    <div className="flex flex-1 items-center justify-center py-6">
                      <QcmChoices
                        choices={q.question.choices}
                        disabled={q.myChoice !== null}
                        myChoice={q.myChoice}
                        correct={null}
                        onPick={submitAnswer}
                      />
                    </div>
                    {q.myChoice !== null && <p className="text-center font-mono text-sm text-muted">Réponse verrouillée — attends les autres…</p>}
                  </>
                )}
              </>
            );
          })()
        ) : q.state === "REVEAL" && q.question ? (
          <div className="flex flex-1 flex-col items-center justify-center">
            <p className={`countdown-pop font-display text-8xl ${won ? "text-volt" : "text-buzz"}`}>{won ? "✓" : "✗"}</p>
            <p className="mt-2 font-display text-2xl">
              {won ? `+${reveal?.deltas[you.id ?? ""] ?? 0} pts` : "Pas cette fois"}
            </p>
            <div className="mt-6 w-full">
              <QcmChoices choices={q.question.choices} disabled myChoice={q.myChoice} correct={reveal?.correct ?? null} onPick={noop} />
            </div>
          </div>
        ) : q.state === "GAME_END" ? (
          <div className="flex flex-1 flex-col justify-center">
            <p className="text-center font-display text-5xl text-volt">Terminé !</p>
            <p className="mt-2 text-center font-display text-2xl">#{me?.rank ?? "—"} · {me?.score ?? 0} pts</p>
            <div className="mt-6"><Scoreboard players={ranking} highlightId={you.id ?? undefined} /></div>
          </div>
        ) : (
          <div className="flex flex-1 flex-col justify-center">
            <p className="text-center font-display text-4xl text-muted">Classement</p>
            <div className="mt-6"><Scoreboard players={ranking} highlightId={you.id ?? undefined} /></div>
          </div>
        )}

        <ScoreFooter rank={me?.rank ?? "—"} score={me?.score ?? 0} />
      </main>
    );
  }

  const b = snapshot.blindtest;
  if (b.mode === "blindtest") {
    const btYouBuzzed = buzz.queue.some((e) => e.player_id === you.id);
    const btYouExcluded = (buzz.excluded_ids ?? []).includes(you.id ?? "");
    const btHasFloor = !!buzz.floor_player_id && buzz.floor_player_id === you.id;
    const btFloorPseudo = players.find((p) => p.id === buzz.floor_player_id)?.pseudo;
    const myDelta = b.reveal?.deltas[you.id ?? ""] ?? 0;
    const wonReveal = myDelta > 0;
    const open = b.state === "BUZZER_OPEN" && buzz.state === "BUZZER_OPEN";
    const canBuzz = open && !btYouBuzzed && !btYouExcluded;

    let label = "BUZZ";
    let sublabel: string | undefined = "Écoute… buzze dès que tu sais !";
    if (b.state === "LOBBY" || b.index < 0) {
      label = "…";
      sublabel = "En attente du blindtest";
    } else if (btHasFloor && buzz.state === "BUZZED") {
      label = "À TOI";
      sublabel = "Donne le titre et/ou l'artiste à voix haute";
    } else if (buzz.state === "BUZZED" && b.state === "BUZZER_OPEN") {
      label = "STOP";
      sublabel = btFloorPseudo ? `${btFloorPseudo} a la main` : "Quelqu'un a buzzé";
    } else if (btYouExcluded && open) {
      // Buzzer reopened (only one of title/artist found, or you answered wrong) but
      // you're barred — make the grayed state legible instead of a stale "BUZZ".
      label = "STOP";
      sublabel = "Tu as déjà répondu — écoute la suite";
    }

    return (
      <main className="flex min-h-screen flex-col px-5 py-5">
        <ScreenHeader code={code} pseudo={me?.pseudo ?? pseudo} connected={snapshot.connected} />

        {b.state === "GAME_END" ? (
          <div className="flex flex-1 flex-col justify-center">
            <p className="text-center font-display text-5xl text-volt">Terminé !</p>
            <p className="mt-2 text-center font-display text-2xl">#{me?.rank ?? "—"} · {me?.score ?? 0} pts</p>
            <div className="mt-6"><Scoreboard players={ranking} highlightId={you.id ?? undefined} /></div>
          </div>
        ) : b.state === "REVEAL" && b.reveal ? (
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <p className={`countdown-pop font-display text-8xl ${wonReveal ? "text-volt" : "text-buzz"}`}>{wonReveal ? "✓" : "✗"}</p>
            <p className="mt-2 font-display text-2xl">{wonReveal ? `+${myDelta} pts` : "Pas cette fois"}</p>
            {b.reveal.cover_url && (
              <CoverImage src={b.reveal.cover_url} size={128} className="mt-6 h-32 w-32 rounded-xl" />
            )}
            <p className="mt-4 font-display text-2xl">{b.reveal.title}</p>
            <p className="font-mono text-sm text-muted">{b.reveal.artist}</p>
          </div>
        ) : b.state === "SCOREBOARD" ? (
          <div className="flex flex-1 flex-col justify-center">
            <p className="text-center font-display text-4xl text-muted">Classement</p>
            <div className="mt-6"><Scoreboard players={ranking} highlightId={you.id ?? undefined} /></div>
          </div>
        ) : (
          <>
            {b.index >= 0 && (
              <p className="mt-6 flex items-center justify-center gap-2 text-center font-mono text-sm text-muted">
                Morceau {b.index + 1}/{b.total}
                {b.bonus && <BonusChip />}
              </p>
            )}
            <BlindtestTimerBar bt={b} />
            {buzz.state === "BUZZED" && (
              (buzz.answer_ends_at ?? 0) > 0 ? (
                <Countdown endsAt={buzz.answer_ends_at ?? 0} offsetMs={b.clockOffset} className="mt-4 text-buzz" />
              ) : (
                <ElapsedTimer offsetMs={b.clockOffset} className="mt-4 block text-center text-buzz" />
              )
            )}
            {!buzz.floor_player_id && b.revealEndsAt > 0 && b.state === "BUZZER_OPEN" && (
              <p className="mt-4 text-center font-mono text-xs text-muted">
                Révélation auto dans <Countdown endsAt={b.revealEndsAt} offsetMs={b.clockOffset} />
              </p>
            )}
            <div className="flex flex-1 flex-col items-center justify-center py-8">
              <Buzzer
                label={label}
                sublabel={sublabel}
                disabled={!canBuzz}
                locked={buzz.state === "BUZZED" && b.state === "BUZZER_OPEN"}
                onBuzz={doBuzz}
              />
            </div>
          </>
        )}

        <ScoreFooter rank={me?.rank ?? "—"} score={me?.score ?? 0} />
      </main>
    );
  }

  // Buzzer game over → podium screen (same as QCM / blindtest).
  if (round.state === "GAME_END") {
    return (
      <main className="flex min-h-screen flex-col px-5 py-5">
        <ScreenHeader code={code} pseudo={me?.pseudo ?? pseudo} connected={snapshot.connected} />
        <div className="flex flex-1 flex-col justify-center">
          <p className="text-center font-display text-5xl text-volt">Terminé !</p>
          <p className="mt-2 text-center font-display text-2xl">#{me?.rank ?? "—"} · {me?.score ?? 0} pts</p>
          <div className="mt-6"><Scoreboard players={ranking} highlightId={you.id ?? undefined} /></div>
        </div>
      </main>
    );
  }

  const youBuzzed = buzz.queue.some((e) => e.player_id === you.id);
  const youExcluded = (buzz.excluded_ids ?? []).includes(you.id ?? "");
  const hasFloor = !!round.floor_player_id && round.floor_player_id === you.id;
  const floorPseudo = players.find((p) => p.id === round.floor_player_id)?.pseudo;
  const wonReveal = round.revealed && reveal?.correct_player_id === you.id;

  // Reading window: buzzer stays locked + shows a "Lecture…" countdown first.
  const buzzReading =
    round.state === "BUZZER_OPEN" && !round.revealed && (round.buzz_open_at ?? 0) > now + (round.clockOffset ?? 0);
  const buzzReadSecs = Math.ceil(((round.buzz_open_at ?? 0) - (now + (round.clockOffset ?? 0))) / 1000);
  const canBuzz =
    round.state === "BUZZER_OPEN" && !round.revealed && !youBuzzed && !buzzReading && !youExcluded;

  let label = "BUZZ";
  let sublabel: string | undefined = "Appuie dès que tu sais !";
  if (round.state === "LOBBY") {
    label = "…";
    sublabel = "En attente du prochain round";
  } else if (buzzReading) {
    label = "LIS";
    sublabel = "Lis la question…";
  } else if (round.revealed) {
    label = wonReveal ? "✓" : "✗";
    sublabel = wonReveal ? "Bien joué !" : round.answer ? `Réponse : ${round.answer}` : "Round terminé";
  } else if (hasFloor) {
    label = "À TOI";
    sublabel = "Réponds à voix haute";
  } else if (round.state === "BUZZED") {
    label = "STOP";
    sublabel = floorPseudo ? `${floorPseudo} a la main` : "Quelqu'un a buzzé";
  } else if (youExcluded) {
    // Buzzer reopened after your wrong answer — you stay locked out this round.
    label = "STOP";
    sublabel = "Mauvaise réponse — laisse les autres";
  }

  return (
    <main className="flex min-h-screen flex-col px-5 py-5">
      {/* Header */}
      <header className="flex items-center justify-between font-mono text-xs text-muted">
        <span className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${snapshot.connected ? "bg-volt" : "bg-buzz"}`} />
          {code}
        </span>
        <span className="truncate">{me?.pseudo ?? pseudo}</span>
      </header>

      {/* Question */}
      {round.question_text && round.state !== "LOBBY" && (
        <p className="mt-6 text-center text-xl">{round.question_text}</p>
      )}
      {round.image && round.state !== "LOBBY" && (
        <PromptImage src={round.image} className="mx-auto mt-3 max-h-44 rounded-lg" />
      )}

      {/* Round time limit bar (auto-reveal when it empties), or a count-up when
          the round has no buzz limit — a timing is always shown. */}
      {round.state === "BUZZER_OPEN" && !round.revealed && !buzzReading && (
        (round.buzz_ends_at ?? 0) > 0 ? (
          <Countdown
            endsAt={round.buzz_ends_at ?? 0}
            offsetMs={round.clockOffset}
            durationMs={(round.buzz_ends_at ?? 0) - (round.buzz_open_at ?? 0)}
            className="mt-4 text-muted"
          />
        ) : (
          <ElapsedTimer
            startedAt={round.buzz_open_at ?? 0}
            offsetMs={round.clockOffset}
            className="mt-4 block text-center text-muted"
          />
        )
      )}

      {/* Post-buzz answer countdown — shown to everyone so the whole room sees
          how long the floor-holder has left (count-up when no answer limit). */}
      {round.state === "BUZZED" && !round.revealed && (
        (buzz.answer_ends_at ?? 0) > 0 ? (
          <Countdown endsAt={buzz.answer_ends_at ?? 0} offsetMs={round.clockOffset} className="mt-4 text-buzz" />
        ) : (
          <ElapsedTimer offsetMs={round.clockOffset} className="mt-4 block text-center text-buzz" />
        )
      )}

      {/* Buzzer (or reading countdown) */}
      <div className="flex flex-1 flex-col items-center justify-center py-8">
        {buzzReading ? (
          <ReadingBadge secondsLeft={buzzReadSecs} label="Lecture…" />
        ) : (
          <Buzzer
            label={label}
            sublabel={sublabel}
            disabled={!canBuzz}
            locked={round.state === "BUZZED" && !round.revealed}
            onBuzz={doBuzz}
          />
        )}
      </div>

      {/* Score */}
      <footer className="flex items-center justify-between rounded-2xl border border-panel2 bg-panel/60 px-5 py-4">
        <span className="font-mono text-xs uppercase tracking-widest text-muted">Ton score</span>
        <span className="flex items-baseline gap-3">
          <span className="font-mono text-sm text-muted">#{me?.rank ?? "—"}</span>
          <span className="font-display text-4xl tabular-nums">{me?.score ?? 0}</span>
        </span>
      </footer>
    </main>
  );
}
