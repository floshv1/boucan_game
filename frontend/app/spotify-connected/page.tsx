"use client";

import { useEffect } from "react";

// Landing page for the Spotify OAuth pop-up (return_to target). The opener polls
// /api/spotify/status and closes us once it sees the linked account; we also try
// to self-close in case polling is slow.
export default function SpotifyConnected() {
  useEffect(() => {
    const id = setTimeout(() => {
      try { window.close(); } catch { /* ignore */ }
    }, 800);
    return () => clearTimeout(id);
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
      <p className="font-display text-3xl text-volt">Spotify connecté ✓</p>
      <p className="font-mono text-sm text-muted">Tu peux fermer cette fenêtre et revenir au jeu.</p>
    </main>
  );
}
