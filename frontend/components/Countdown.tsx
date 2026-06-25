"use client";

import { useEffect, useRef, useState } from "react";

import * as sfx from "@/lib/sfx";

// Renders the seconds left until `endsAt` (server ms), ticking locally.
// `offsetMs` corrects for clock skew between this device and the server (estimated
// when the question started — see the question_start reducer). The last three
// seconds play a tick so players feel the pressure.
export default function Countdown({ endsAt, offsetMs = 0 }: { endsAt: number; offsetMs?: number }) {
  const [now, setNow] = useState(() => Date.now());
  const lastTickRef = useRef<number>(-1);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

  const left = Math.max(0, Math.ceil((endsAt - (now + offsetMs)) / 1000));

  useEffect(() => {
    if (left !== lastTickRef.current) {
      if (left > 0 && left <= 3) sfx.tick();
      lastTickRef.current = left;
    }
  }, [left]);

  return <span className="font-display tabular-nums">{left}s</span>;
}
