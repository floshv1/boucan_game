"use client";

import MuteToggle from "@/components/MuteToggle";

// Player-view top bar: connection dot + game code on the left, pseudo (and the
// mute toggle, where sound matters) on the right. Was repeated 4× in the player
// screen across game modes.
interface Props {
  code: string;
  pseudo: string;
  connected: boolean;
  showMute?: boolean;
}

export default function ScreenHeader({ code, pseudo, connected, showMute = true }: Props) {
  return (
    <header className="flex items-center justify-between font-mono text-xs text-muted">
      <span className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${connected ? "bg-volt" : "bg-buzz"}`} />
        {code}
      </span>
      <span className="flex items-center gap-2">
        <span className="max-w-[40vw] truncate">{pseudo}</span>
        {showMute && <MuteToggle />}
      </span>
    </header>
  );
}
