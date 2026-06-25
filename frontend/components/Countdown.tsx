"use client";

import { useEffect, useRef, useState } from "react";

import * as sfx from "@/lib/sfx";

// Renders the seconds left until `endsAt` (server ms), ticking locally.
// `offsetMs` corrects for clock skew between this device and the server (estimated
// when the question started — see the question_start reducer). The last three
// seconds play a tick so players feel the pressure.
//
// When `durationMs` is provided, a depleting progress bar is shown above the
// number, mirroring the blindtest play bar so every timed mode looks the same.
export default function Countdown({
  endsAt,
  offsetMs = 0,
  durationMs,
  className = "",
}: {
  endsAt: number;
  offsetMs?: number;
  durationMs?: number;
  className?: string;
}) {
  const [now, setNow] = useState(() => Date.now());
  const lastTickRef = useRef<number>(-1);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

  const remainingMs = Math.max(0, endsAt - (now + offsetMs));
  const left = Math.ceil(remainingMs / 1000);

  useEffect(() => {
    if (left !== lastTickRef.current) {
      if (left > 0 && left <= 3) sfx.tick();
      lastTickRef.current = left;
    }
  }, [left]);

  if (durationMs && durationMs > 0) {
    const progress = Math.max(0, Math.min(1, remainingMs / durationMs));
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <div className="h-2 flex-1 rounded bg-panel2">
          <div
            className={`h-2 rounded transition-[width] duration-200 ease-linear ${
              left <= 3 ? "bg-buzz" : "bg-volt"
            }`}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
        <span className="font-display tabular-nums">{left}s</span>
      </div>
    );
  }

  return <span className={`font-display tabular-nums ${className}`}>{left}s</span>;
}
