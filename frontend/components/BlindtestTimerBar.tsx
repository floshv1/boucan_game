"use client";

import { useEffect, useRef, useState } from "react";

import * as sfx from "@/lib/sfx";
import { BlindtestState } from "@/lib/types";

// Synced 3-2-1 countdown + play progress for players/TV. Pause-aware and
// clock-skew-safe: progress is driven by accumulated *played* time and frozen
// when the host pauses or someone buzzes; the server clock is estimated via
// bt.clockOffset so it stays correct across devices with different clocks.
export default function BlindtestTimerBar({ bt }: { bt: BlindtestState }) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

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

  if (bt.segStartedAt <= 0) return null;
  const estServerNow = nowMs + bt.clockOffset;

  // Countdown: only while the segment clock is running and not yet reached.
  if (bt.playing && estServerNow < bt.segStartedAt) {
    return (
      <div className="my-4 text-center font-display text-7xl text-volt">
        {Math.ceil((bt.segStartedAt - estServerNow) / 1000)}
      </div>
    );
  }

  if (bt.maxPlayMs > 0) {
    const elapsed = bt.playing
      ? bt.playedMs + Math.max(0, estServerNow - bt.segStartedAt)
      : bt.playedMs;
    const progress = Math.min(1, elapsed / bt.maxPlayMs);
    return (
      <div className="mx-auto my-4 h-2 w-full max-w-md rounded bg-panel2">
        <div
          className="h-2 rounded bg-volt transition-all"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
    );
  }

  return null;
}
