"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import AnswerBars from "@/components/AnswerBars";
import BlindtestTimerBar from "@/components/BlindtestTimerBar";
import BonusChip from "@/components/BonusChip";
import BuzzStrip from "@/components/BuzzStrip";
import Card from "@/components/Card";
import Countdown from "@/components/Countdown";
import ElapsedTimer from "@/components/ElapsedTimer";
import Equalizer from "@/components/Equalizer";
import JoinCard from "@/components/JoinCard";
import { CoverImage, PromptImage } from "@/components/MediaImage";
import { ANSWER_SHAPE, ANSWER_TILE } from "@/components/QcmChoices";
import RankList, { RankRow } from "@/components/RankList";
import ReadingBadge from "@/components/ReadingBadge";
import Scoreboard from "@/components/Scoreboard";
import { useGameSocket } from "@/lib/useGameSocket";
import { useNow } from "@/lib/useNow";

// Public shared screen (TV / projector). Read-only spectator: it shows the
// question, the buzz order and the scores — but the backend never sends it the
// answer before reveal (cahier §16). No buzzer, no controls.
export default function TvView() {
  const code = String(useParams().code ?? "").toUpperCase();
  const [joinUrl, setJoinUrl] = useState("");

  useEffect(() => {
    setJoinUrl(`${window.location.origin}/play?code=${code}`);
  }, [code]);

  const { snapshot } = useGameSocket({ code, role: "tv" });
  const now = useNow();
  const { round, players, buzz, reveal, connected } = snapshot;
  const state = round.state;
  const leader = players[0];
  const bt = snapshot.blindtest;
  const isBt = bt.mode === "blindtest";
  const ranking = [...players].sort((a, b) => a.rank - b.rank);

  // QCM reading window (choices hidden until they unlock).
  const qcmQ = snapshot.qcm.question;
  const qcmReading = !!qcmQ && (qcmQ.choices_at ?? 0) > now + snapshot.qcm.clockOffset;
  const qcmReadSecs = qcmQ ? Math.ceil(((qcmQ.choices_at ?? 0) - (now + snapshot.qcm.clockOffset)) / 1000) : 0;

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col px-8 py-8">
      {/* Header: branding + connection + join card */}
      <header className="flex items-start justify-between gap-6">
        <div>
          <p className="flex items-end gap-2 font-display text-5xl tracking-[0.08em] text-buzz">
            BOUCAN <Equalizer bars={4} className="mb-1 h-7" />
          </p>
          <p className="mt-1 flex items-center gap-2 font-mono text-sm text-muted">
            <span className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-volt" : "bg-buzz"}`} />
            {players.length} joueur{players.length > 1 ? "s" : ""}
            {round.round_total > 0 && state !== "LOBBY" && (
              <span className="ml-2 text-cream/70">
                Round {round.round_index + 1}/{round.round_total}
              </span>
            )}
            {isBt && bt.index >= 0 && bt.state !== "GAME_END" && (
              <span className="ml-2 text-cream/70">
                Morceau {bt.index + 1}/{bt.total}
              </span>
            )}
          </p>
        </div>
        <JoinCard code={code} joinUrl={joinUrl} size={120} />
      </header>

      <div className="mt-6 grid flex-1 gap-8 lg:grid-cols-[1.5fr_1fr]">
        {/* Stage: question + buzz order */}
        <section className="flex flex-col">
          {snapshot.qcm.mode === "qcm" ? (
            <Card className="flex flex-1 flex-col items-center justify-center px-8 py-10 text-center">
              {snapshot.qcm.state === "GAME_END" ? (
                <div className="w-full">
                  <p className="font-display text-5xl text-volt">Podium 🏆</p>
                  <RankList
                    variant="podium"
                    animate
                    className="mt-8"
                    rows={(snapshot.qcm.gameEnd?.podium ?? []) as RankRow[]}
                  />
                </div>
              ) : snapshot.qcm.state === "SCOREBOARD" ? (
                <div className="w-full">
                  <p className="mb-6 font-display text-4xl">Classement</p>
                  <RankList variant="scoreboard" rows={snapshot.qcm.scoreboard.slice(0, 8) as RankRow[]} />
                </div>
              ) : snapshot.qcm.state === "REVEAL" && snapshot.qcm.question && snapshot.qcm.reveal ? (
                <div className="w-full">
                  <p className="mb-6 font-display text-4xl">{snapshot.qcm.question.question}</p>
                  <AnswerBars
                    choices={snapshot.qcm.question.choices}
                    distribution={snapshot.qcm.reveal.distribution}
                    correct={snapshot.qcm.reveal.correct}
                  />
                </div>
              ) : snapshot.qcm.question ? (
                <div className="w-full">
                  <div className="mb-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 font-mono text-xl text-muted">
                    <span className="flex items-center gap-2">
                      Question {snapshot.qcm.index + 1}/{snapshot.qcm.total}
                      {snapshot.qcm.question.bonus && <BonusChip />}
                    </span>
                    <span>{snapshot.qcm.progress.answered}/{snapshot.qcm.progress.total} ✓</span>
                  </div>
                  {!qcmReading && (
                    <Countdown
                      endsAt={snapshot.qcm.question.ends_at}
                      offsetMs={snapshot.qcm.clockOffset}
                      durationMs={snapshot.qcm.question.time_limit * 1000}
                      className="mx-auto mb-6 max-w-xl text-2xl"
                    />
                  )}
                  <p className="font-display text-display-2xl">{snapshot.qcm.question.question}</p>
                  {snapshot.qcm.question.image && (
                    <PromptImage src={snapshot.qcm.question.image} className="mx-auto mt-6 max-h-64 rounded-xl" />
                  )}
                  {qcmReading ? (
                    <ReadingBadge secondsLeft={qcmReadSecs} className="mt-8" />
                  ) : (
                    <div className="mt-8 grid grid-cols-2 gap-4">
                      {snapshot.qcm.question.choices.map((c, i) => (
                        <div
                          key={i}
                          className={`flex items-center gap-3 rounded-2xl px-6 py-6 text-left font-display text-3xl text-white ${ANSWER_TILE[i]}`}
                        >
                          <span className="text-2xl">{ANSWER_SHAPE[i]}</span>
                          <span className="flex-1">{c}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <p className="font-display text-4xl text-muted">En attente…</p>
              )}
            </Card>
          ) : null}

          {isBt && snapshot.qcm.mode !== "qcm" && (
            <Card className="flex flex-1 flex-col items-center justify-center px-8 py-12 text-center">
              {bt.state === "GAME_END" ? (
                <div className="w-full">
                  <p className="font-display text-5xl text-volt">Podium 🏆</p>
                  <RankList variant="podium" animate className="mt-8" rows={(bt.gameEnd?.podium ?? []) as RankRow[]} />
                </div>
              ) : bt.state === "SCOREBOARD" ? (
                <div className="w-full">
                  <p className="mb-6 font-display text-4xl">Classement</p>
                  <RankList variant="scoreboard" rows={bt.scoreboard.slice(0, 8) as RankRow[]} />
                </div>
              ) : bt.state === "REVEAL" && bt.reveal ? (
                <div className="flex flex-col items-center">
                  {bt.reveal.cover_url && (
                    <CoverImage src={bt.reveal.cover_url} size={176} className="countdown-pop h-44 w-44 rounded-2xl" />
                  )}
                  <p className="mt-6 font-display text-5xl text-volt">{bt.reveal.title}</p>
                  <p className="mt-2 font-display text-3xl text-cream/80">{bt.reveal.artist}</p>
                </div>
              ) : bt.index >= 0 ? (
                <div className="flex flex-col items-center">
                  <div className="flex h-44 w-44 items-center justify-center rounded-2xl border border-panel2 bg-ink/50 font-display text-7xl text-muted">
                    ?
                  </div>
                  <p className="mt-6 flex items-center justify-center gap-3 font-display text-4xl">
                    Morceau {bt.index + 1}/{bt.total}
                    {bt.bonus && <BonusChip className="text-base" />}
                  </p>
                  <BlindtestTimerBar bt={bt} />
                  <Equalizer bars={9} animated={bt.playing} className="mt-2 h-10" />
                  <p className="mt-3 font-display text-2xl text-muted">À l&apos;écoute… buzze dès que tu sais !</p>
                </div>
              ) : (
                <p className="font-display text-4xl text-muted">En attente du blindtest…</p>
              )}
            </Card>
          )}

          {snapshot.qcm.mode !== "qcm" && !isBt && (
            <Card className="flex flex-1 flex-col items-center justify-center px-8 py-12 text-center">
              {state === "GAME_END" ? (
                <div className="w-full">
                  <p className="font-display text-5xl text-volt">Podium 🏆</p>
                  <RankList variant="podium" animate className="mt-8" rows={ranking.slice(0, 3) as RankRow[]} />
                </div>
              ) : state === "LOBBY" ? (
                <p className="font-display text-4xl text-muted">En attente du prochain round…</p>
              ) : round.question_text ? (
                <div className="flex flex-col items-center">
                  <p className="font-display text-display-2xl">{round.question_text}</p>
                  {round.image && (
                    <PromptImage src={round.image} className="mt-6 max-h-64 rounded-xl" />
                  )}
                  {(round.buzz_open_at ?? 0) > now + (round.clockOffset ?? 0) && !round.revealed && (
                    <ReadingBadge
                      secondsLeft={Math.ceil(((round.buzz_open_at ?? 0) - (now + (round.clockOffset ?? 0))) / 1000)}
                      className="mt-8"
                    />
                  )}
                </div>
              ) : (
                <p className="font-display text-5xl text-muted">À l&apos;écoute… buzze dès que tu sais !</p>
              )}

              {state === "BUZZER_OPEN" &&
                !round.revealed &&
                (round.buzz_open_at ?? 0) <= now + (round.clockOffset ?? 0) && (
                  (round.buzz_ends_at ?? 0) > 0 ? (
                    <Countdown
                      endsAt={round.buzz_ends_at ?? 0}
                      offsetMs={round.clockOffset}
                      durationMs={(round.buzz_ends_at ?? 0) - (round.buzz_open_at ?? 0)}
                      className="mx-auto mt-8 max-w-xl text-2xl"
                    />
                  ) : (
                    <ElapsedTimer
                      startedAt={round.buzz_open_at ?? 0}
                      offsetMs={round.clockOffset}
                      className="mt-8 block text-2xl"
                    />
                  )
                )}

              {buzz.state === "BUZZED" && buzz.floor_player_id && (
                (buzz.answer_ends_at ?? 0) > 0 ? (
                  <Countdown
                    endsAt={buzz.answer_ends_at ?? 0}
                    offsetMs={isBt ? bt.clockOffset : round.clockOffset}
                    className="mx-auto mt-8 max-w-xl text-2xl text-buzz"
                  />
                ) : (
                  <ElapsedTimer
                    offsetMs={isBt ? bt.clockOffset : round.clockOffset}
                    className="mt-8 block text-2xl text-buzz"
                  />
                )
              )}

              {isBt && !buzz.floor_player_id && bt.revealEndsAt > 0 && bt.state === "BUZZER_OPEN" && (
                <p className="mt-8 flex items-center justify-center gap-3 font-mono text-xl text-muted">
                  Révélation dans
                  <Countdown endsAt={bt.revealEndsAt} offsetMs={bt.clockOffset} className="text-2xl" />
                </p>
              )}

              {reveal && state !== "GAME_END" && (
                <p className="animate-reveal-flash mt-8 rounded-2xl border border-volt/40 bg-volt/10 px-6 py-4 font-display text-3xl text-volt">
                  {reveal.answer ? `Réponse : ${reveal.answer}` : "Round terminé"}
                </p>
              )}
            </Card>
          )}

          {buzz.queue.length > 0 && snapshot.qcm.mode !== "qcm" && (!isBt || bt.state === "BUZZER_OPEN") && (
            <Card className="mt-6 p-5">
              <p className="mb-3 font-mono text-xs uppercase tracking-[0.3em] text-muted">Ordre des buzz</p>
              <BuzzStrip queue={buzz.queue} floorPlayerId={isBt ? buzz.floor_player_id : round.floor_player_id} />
            </Card>
          )}
        </section>

        {/* Scoreboard (read-only) */}
        <Card as="section" className="p-6">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="font-display text-4xl">Scores</h2>
            {leader && players.length > 1 && (
              <span className="font-mono text-sm text-volt">👑 {leader.pseudo}</span>
            )}
          </div>
          <Scoreboard players={players} highlightId={(isBt ? buzz.floor_player_id : round.floor_player_id) ?? undefined} />
        </Card>
      </div>
    </main>
  );
}
