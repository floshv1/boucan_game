"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import AnswerBars from "@/components/AnswerBars";
import BlindtestTimerBar from "@/components/BlindtestTimerBar";
import BonusChip from "@/components/BonusChip";
import BuzzStrip from "@/components/BuzzStrip";
import Countdown from "@/components/Countdown";
import Equalizer from "@/components/Equalizer";
import JoinCard from "@/components/JoinCard";
import Scoreboard from "@/components/Scoreboard";
import { useGameSocket } from "@/lib/useGameSocket";

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
  const { round, players, buzz, reveal, connected } = snapshot;
  const state = round.state;
  const leader = players[0];
  const bt = snapshot.blindtest;
  const isBt = bt.mode === "blindtest";

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
            <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border border-panel2 bg-panel/50 px-8 py-10 text-center">
              {snapshot.qcm.state === "GAME_END" ? (
                <div className="w-full">
                  <p className="font-display text-5xl text-volt">Podium 🏆</p>
                  <ol className="mx-auto mt-8 flex max-w-xl flex-col gap-3">
                    {(snapshot.qcm.gameEnd?.podium ?? []).map((p) => (
                      <li key={p.id} className="flex items-center justify-between rounded-2xl border border-panel2 bg-panel px-6 py-4">
                        <span className="font-display text-3xl">{p.rank}. {p.pseudo}</span>
                        <span className="font-display text-3xl tabular-nums text-volt">{p.score}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : snapshot.qcm.state === "SCOREBOARD" ? (
                <div className="w-full">
                  <p className="mb-6 font-display text-4xl">Classement</p>
                  <ol className="mx-auto flex max-w-xl flex-col gap-2">
                    {snapshot.qcm.scoreboard.slice(0, 8).map((r) => (
                      <li key={r.id} className="flex items-center justify-between rounded-xl border border-panel2 bg-panel px-5 py-3">
                        <span className="font-display text-2xl">
                          {r.rank}. {r.pseudo}{" "}
                          <span className={r.delta > 0 ? "text-volt" : r.delta < 0 ? "text-buzz" : "text-muted"}>
                            {r.delta > 0 ? "▲" : r.delta < 0 ? "▼" : "·"}
                          </span>
                        </span>
                        <span className="font-display text-2xl tabular-nums">{r.score}</span>
                      </li>
                    ))}
                  </ol>
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
                    <span><Countdown endsAt={snapshot.qcm.question.ends_at} offsetMs={snapshot.qcm.clockOffset} /></span>
                    <span>{snapshot.qcm.progress.answered}/{snapshot.qcm.progress.total} ✓</span>
                  </div>
                  <p className="font-display text-6xl leading-tight">{snapshot.qcm.question.question}</p>
                  {snapshot.qcm.question.image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={snapshot.qcm.question.image} alt="" className="mx-auto mt-6 max-h-64 rounded-xl object-contain" />
                  )}
                  <div className="mt-8 grid grid-cols-2 gap-4">
                    {snapshot.qcm.question.choices.map((c, i) => (
                      <div key={i} className={`rounded-2xl px-6 py-6 font-display text-3xl text-white ${["bg-buzz", "bg-blue-500", "bg-yellow-400 text-ink", "bg-volt text-ink"][i]}`}>
                        {c}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="font-display text-4xl text-muted">En attente…</p>
              )}
            </div>
          ) : null}

          {isBt && snapshot.qcm.mode !== "qcm" && (
            <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border border-panel2 bg-panel/50 px-8 py-12 text-center">
              {bt.state === "GAME_END" ? (
                <div className="w-full">
                  <p className="font-display text-5xl text-volt">Podium 🏆</p>
                  <ol className="mx-auto mt-8 flex max-w-xl flex-col gap-3">
                    {(bt.gameEnd?.podium ?? []).map((p) => (
                      <li key={p.id} className="flex items-center justify-between rounded-2xl border border-panel2 bg-panel px-6 py-4">
                        <span className="font-display text-3xl">{p.rank}. {p.pseudo}</span>
                        <span className="font-display text-3xl tabular-nums text-volt">{p.score}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : bt.state === "SCOREBOARD" ? (
                <div className="w-full">
                  <p className="mb-6 font-display text-4xl">Classement</p>
                  <ol className="mx-auto flex max-w-xl flex-col gap-2">
                    {bt.scoreboard.slice(0, 8).map((r) => (
                      <li key={r.id} className="flex items-center justify-between rounded-xl border border-panel2 bg-panel px-5 py-3">
                        <span className="font-display text-2xl">
                          {r.rank}. {r.pseudo}{" "}
                          <span className={r.delta > 0 ? "text-volt" : r.delta < 0 ? "text-buzz" : "text-muted"}>
                            {r.delta > 0 ? "▲" : r.delta < 0 ? "▼" : "·"}
                          </span>
                        </span>
                        <span className="font-display text-2xl tabular-nums">{r.score}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : bt.state === "REVEAL" && bt.reveal ? (
                <div className="flex flex-col items-center">
                  {bt.reveal.cover_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={bt.reveal.cover_url} alt="" className="h-44 w-44 rounded-2xl object-cover" />
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
                  <p className="mt-2 font-display text-2xl text-muted">À l&apos;écoute… buzze dès que tu sais !</p>
                </div>
              ) : (
                <p className="font-display text-4xl text-muted">En attente du blindtest…</p>
              )}
            </div>
          )}

          {snapshot.qcm.mode !== "qcm" && !isBt && (
            <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border border-panel2 bg-panel/50 px-8 py-12 text-center">
              {state === "LOBBY" ? (
                <p className="font-display text-4xl text-muted">En attente du prochain round…</p>
              ) : round.question_text ? (
                <div className="flex flex-col items-center">
                  <p className="font-display text-6xl leading-tight">{round.question_text}</p>
                  {round.image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={round.image} alt="" className="mt-6 max-h-64 rounded-xl object-contain" />
                  )}
                </div>
              ) : (
                <p className="font-display text-5xl text-muted">À l&apos;écoute… buzze dès que tu sais !</p>
              )}

              {reveal && (
                <p className="mt-8 rounded-2xl border border-volt/40 bg-volt/10 px-6 py-4 font-display text-3xl text-volt">
                  {reveal.answer ? `Réponse : ${reveal.answer}` : "Round terminé"}
                </p>
              )}
            </div>
          )}

          {buzz.queue.length > 0 && snapshot.qcm.mode !== "qcm" && (!isBt || bt.state === "BUZZER_OPEN") && (
            <div className="mt-6 rounded-3xl border border-panel2 bg-panel/50 p-5">
              <p className="mb-3 font-mono text-xs uppercase tracking-[0.3em] text-muted">Ordre des buzz</p>
              <BuzzStrip queue={buzz.queue} floorPlayerId={isBt ? buzz.floor_player_id : round.floor_player_id} />
            </div>
          )}
        </section>

        {/* Scoreboard (read-only) */}
        <section className="rounded-3xl border border-panel2 bg-panel/50 p-6">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="font-display text-4xl">Scores</h2>
            {leader && players.length > 1 && (
              <span className="font-mono text-sm text-volt">👑 {leader.pseudo}</span>
            )}
          </div>
          <Scoreboard players={players} highlightId={(isBt ? buzz.floor_player_id : round.floor_player_id) ?? undefined} />
        </section>
      </div>
    </main>
  );
}
