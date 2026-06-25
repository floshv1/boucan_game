"use client";

import { memo } from "react";

import { PlayerInfo } from "@/lib/types";

interface Props {
  players: PlayerInfo[];
  // Host-only controls. Omit for a read-only board.
  onAdjust?: (playerId: string, delta: number) => void;
  onKick?: (playerId: string) => void;
  highlightId?: string;
}

function Scoreboard({ players, onAdjust, onKick, highlightId }: Props) {
  if (players.length === 0) {
    return <p className="text-muted">Personne n&apos;a encore rejoint.</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {players.map((p) => (
        <li
          key={p.id}
          className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 ${
            p.id === highlightId ? "border-volt bg-volt/10" : "border-panel2 bg-panel"
          } ${p.connected ? "" : "opacity-50"}`}
        >
          <span className="w-6 font-display text-xl text-muted">{p.rank}</span>
          <span className="flex-1 truncate">
            <span className="text-lg">{p.pseudo}</span>
            {!p.connected && <span className="ml-2 font-mono text-xs text-muted">hors-ligne</span>}
          </span>
          <span className="font-display text-2xl tabular-nums">{p.score}</span>
          {onAdjust && (
            <span className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onAdjust(p.id, -1)}
                className="h-8 w-8 rounded-lg bg-panel2 text-xl leading-none hover:bg-buzzdeep"
                aria-label={`Retirer un point à ${p.pseudo}`}
              >
                −
              </button>
              <button
                type="button"
                onClick={() => onAdjust(p.id, 1)}
                className="h-8 w-8 rounded-lg bg-panel2 text-xl leading-none hover:bg-volt hover:text-ink"
                aria-label={`Ajouter un point à ${p.pseudo}`}
              >
                +
              </button>
            </span>
          )}
          {onKick && (
            <button
              type="button"
              onClick={() => onKick(p.id)}
              className="h-8 w-8 rounded-lg text-muted hover:bg-buzzdeep hover:text-white"
              aria-label={`Exclure ${p.pseudo}`}
            >
              ✕
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

export default memo(Scoreboard);
