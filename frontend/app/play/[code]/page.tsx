"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import BlindtestTimerBar from "@/components/BlindtestTimerBar";
import BonusChip from "@/components/BonusChip";
import Buzzer from "@/components/Buzzer";
import Countdown from "@/components/Countdown";
import MuteToggle from "@/components/MuteToggle";
import QcmChoices from "@/components/QcmChoices";
import Scoreboard from "@/components/Scoreboard";
import * as sfx from "@/lib/sfx";
import { useGameSocket } from "@/lib/useGameSocket";

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
        <header className="flex items-center justify-between font-mono text-xs text-muted">
          <span className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${snapshot.connected ? "bg-volt" : "bg-buzz"}`} />
            {code}
          </span>
          <span className="flex items-center gap-2">
            <span className="max-w-[40vw] truncate">{me?.pseudo ?? pseudo}</span>
            <MuteToggle />
          </span>
        </header>

        {q.state === "QUESTION_ACTIVE" && q.question ? (
          <>
            <div className="mt-4 flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 font-mono text-xs text-muted">
                Question {q.index + 1}/{q.total}
                {q.question.bonus && <BonusChip />}
              </span>
              <span className="font-mono text-sm text-muted"><Countdown endsAt={q.question.ends_at} offsetMs={q.clockOffset} /></span>
            </div>
            <p className="mt-3 text-center text-lg">{q.question.question}</p>
            {q.question.image && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={q.question.image} alt="" className="mx-auto mt-3 max-h-40 rounded-lg object-contain" />
            )}
            <div className="flex flex-1 items-center justify-center py-6">
              <QcmChoices
                choices={q.question.choices}
                disabled={q.myChoice !== null}
                myChoice={q.myChoice}
                correct={null}
                onPick={(i) => send("answer_submit", { choice: i })}
              />
            </div>
            {q.myChoice !== null && <p className="text-center font-mono text-sm text-muted">Réponse verrouillée — attends les autres…</p>}
          </>
        ) : q.state === "REVEAL" && q.question ? (
          <div className="flex flex-1 flex-col items-center justify-center">
            <p className="font-display text-7xl">{won ? "✓" : "✗"}</p>
            <p className="mt-2 text-cream/80">
              {won ? `+${reveal?.deltas[you.id ?? ""] ?? 0} pts` : "Pas cette fois"}
            </p>
            <div className="mt-6 w-full">
              <QcmChoices choices={q.question.choices} disabled myChoice={q.myChoice} correct={reveal?.correct ?? null} onPick={() => {}} />
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

  const b = snapshot.blindtest;
  if (b.mode === "blindtest") {
    const btYouBuzzed = buzz.queue.some((e) => e.player_id === you.id);
    const btHasFloor = !!buzz.floor_player_id && buzz.floor_player_id === you.id;
    const btFloorPseudo = players.find((p) => p.id === buzz.floor_player_id)?.pseudo;
    const myDelta = b.reveal?.deltas[you.id ?? ""] ?? 0;
    const wonReveal = myDelta > 0;
    const open = b.state === "BUZZER_OPEN" && buzz.state === "BUZZER_OPEN";
    const canBuzz = open && !btYouBuzzed;

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
    }

    return (
      <main className="flex min-h-screen flex-col px-5 py-5">
        <header className="flex items-center justify-between font-mono text-xs text-muted">
          <span className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${snapshot.connected ? "bg-volt" : "bg-buzz"}`} />
            {code}
          </span>
          <span className="flex items-center gap-2">
            <span className="max-w-[40vw] truncate">{me?.pseudo ?? pseudo}</span>
            <MuteToggle />
          </span>
        </header>

        {b.state === "GAME_END" ? (
          <div className="flex flex-1 flex-col justify-center">
            <p className="text-center font-display text-5xl text-volt">Terminé !</p>
            <p className="mt-2 text-center font-display text-2xl">#{me?.rank ?? "—"} · {me?.score ?? 0} pts</p>
            <div className="mt-6"><Scoreboard players={ranking} highlightId={you.id ?? undefined} /></div>
          </div>
        ) : b.state === "REVEAL" && b.reveal ? (
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <p className="font-display text-7xl">{wonReveal ? "✓" : "✗"}</p>
            <p className="mt-2 text-cream/80">{wonReveal ? `+${myDelta} pts` : "Pas cette fois"}</p>
            {b.reveal.cover_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={b.reveal.cover_url} alt="" className="mt-6 h-32 w-32 rounded-xl object-cover" />
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
            <div className="flex flex-1 flex-col items-center justify-center py-8">
              <Buzzer
                label={label}
                sublabel={sublabel}
                disabled={!canBuzz}
                locked={buzz.state === "BUZZED" && b.state === "BUZZER_OPEN"}
                onBuzz={() => { sfx.buzz(); send("buzz"); }}
              />
            </div>
          </>
        )}

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

  const youBuzzed = buzz.queue.some((e) => e.player_id === you.id);
  const hasFloor = !!round.floor_player_id && round.floor_player_id === you.id;
  const floorPseudo = players.find((p) => p.id === round.floor_player_id)?.pseudo;
  const wonReveal = round.revealed && reveal?.correct_player_id === you.id;

  const canBuzz = round.state === "BUZZER_OPEN" && !round.revealed && !youBuzzed;
  const locked = !canBuzz;

  let label = "BUZZ";
  let sublabel: string | undefined = "Appuie dès que tu sais !";
  if (round.state === "LOBBY") {
    label = "…";
    sublabel = "En attente du prochain round";
  } else if (round.revealed) {
    label = wonReveal ? "✓" : "✗";
    sublabel = wonReveal ? "Bien joué !" : round.answer ? `Réponse : ${round.answer}` : "Round terminé";
  } else if (hasFloor) {
    label = "À TOI";
    sublabel = "Réponds à voix haute";
  } else if (round.state === "BUZZED") {
    label = "STOP";
    sublabel = floorPseudo ? `${floorPseudo} a la main` : "Quelqu'un a buzzé";
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
        // eslint-disable-next-line @next/next/no-img-element
        <img src={round.image} alt="" className="mx-auto mt-3 max-h-44 rounded-lg object-contain" />
      )}

      {/* Buzzer */}
      <div className="flex flex-1 flex-col items-center justify-center py-8">
        <Buzzer
          label={label}
          sublabel={sublabel}
          disabled={!canBuzz}
          locked={round.state === "BUZZED" && !round.revealed}
          onBuzz={() => { sfx.buzz(); send("buzz"); }}
        />
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
