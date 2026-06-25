"use client";

import { useEffect, useState } from "react";

import { isMuted, setMuted, subscribeMuted } from "@/lib/sfx";

// Small 🔊 / 🔇 toggle for the in-app sound effects. State lives in localStorage
// (see lib/sfx) so it persists and stays in sync across components.
export default function MuteToggle({ className = "" }: { className?: string }) {
  const [muted, setMutedState] = useState(false);

  useEffect(() => {
    setMutedState(isMuted());
    return subscribeMuted(setMutedState);
  }, []);

  return (
    <button
      type="button"
      onClick={() => setMuted(!muted)}
      aria-pressed={muted}
      aria-label={muted ? "Activer le son" : "Couper le son"}
      title={muted ? "Activer le son" : "Couper le son"}
      className={`flex min-h-[36px] min-w-[36px] items-center justify-center rounded-lg border border-panel2 text-base transition hover:border-muted ${className}`}
    >
      {muted ? "🔇" : "🔊"}
    </button>
  );
}
