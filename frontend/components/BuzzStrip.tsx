"use client";

import Equalizer from "@/components/Equalizer";
import { BuzzEntry } from "@/lib/types";

interface Props {
  queue: BuzzEntry[];
  floorPlayerId: string | null;
}

// The buzz order as a photo-finish strip: rank, who, and the millisecond gap
// behind the leader (cahier §14).
export default function BuzzStrip({ queue, floorPlayerId }: Props) {
  if (queue.length === 0) {
    return <p className="font-mono text-sm text-muted">En attente des buzzes…</p>;
  }
  return (
    <ol className="flex flex-col gap-2">
      {queue.map((e) => {
        const isFloor = e.player_id === floorPlayerId;
        const isLeader = e.order === 1;
        return (
          <li
            key={e.player_id}
            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 ${
              isFloor ? "bg-volt/15 ring-2 ring-volt" : "bg-ink/40"
            }`}
          >
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg font-display text-lg ${
                isLeader ? "bg-volt text-ink" : "bg-panel2 text-cream"
              }`}
            >
              {e.order}
            </span>
            <span className="flex-1 truncate text-lg">{e.pseudo}</span>
            {isFloor && <Equalizer bars={3} className="h-4" />}
            <span className="font-mono text-sm text-muted">{isLeader ? "leader" : `+${e.delta_ms}ms`}</span>
          </li>
        );
      })}
    </ol>
  );
}
