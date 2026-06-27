"use client";

import { useEffect, useRef, useState } from "react";

// Counts UP from the moment it mounts — used as a fallback when a phase has no
// configured time limit (so a timing is always visible). It is only mounted
// while the relevant phase is active, so mount ≈ phase start. Mirrors the
// `font-display tabular-nums` look of <Countdown> so timed/untimed modes match.
//
// `startedAt` (server ms) + `offsetMs` let the caller anchor the count to a real
// server moment when one is available; otherwise it counts from mount.
export default function ElapsedTimer({
  startedAt,
  offsetMs = 0,
  className = "",
}: {
  startedAt?: number;
  offsetMs?: number;
  className?: string;
}) {
  const mountRef = useRef<number>(Date.now());
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

  const start = startedAt && startedAt > 0 ? startedAt - offsetMs : mountRef.current;
  const elapsed = Math.max(0, Math.floor((now - start) / 1000));
  const label = elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;

  return <span className={`font-display tabular-nums ${className}`}>{label}</span>;
}
