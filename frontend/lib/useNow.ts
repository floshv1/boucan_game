"use client";

import { useEffect, useState } from "react";

// Ticking clock for time-driven UI (reading windows, countdowns). Returns Date.now()
// refreshed every `intervalMs`. Add a server clock offset to compare against server
// timestamps.
export function useNow(intervalMs = 250): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
