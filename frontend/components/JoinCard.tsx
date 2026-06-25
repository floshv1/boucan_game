"use client";

import { QRCodeSVG } from "qrcode.react";

interface Props {
  code: string;
  joinUrl: string;
  size?: number;
}

// Shows the game code big plus a QR that points at the player join URL, so a
// phone on the same WiFi joins by scanning — no typing the code.
export default function JoinCard({ code, joinUrl, size = 132 }: Props) {
  return (
    <div className="flex items-center gap-5">
      <div className="rounded-2xl bg-cream p-3">
        {joinUrl ? (
          <QRCodeSVG value={joinUrl} size={size} bgColor="#FBF4E6" fgColor="#1A1230" level="M" />
        ) : (
          <div style={{ width: size, height: size }} />
        )}
      </div>
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted">Code</p>
        <p className="font-display leading-none tracking-[0.12em] text-volt" style={{ fontSize: size * 0.42 }}>
          {code}
        </p>
        <p className="mt-2 max-w-[16ch] break-words font-mono text-xs text-muted">
          {joinUrl.replace(/^https?:\/\//, "")}
        </p>
      </div>
    </div>
  );
}
