"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import Button from "@/components/Button";
import { backendHttpUrl } from "@/lib/backend";

interface SpotifyStatus {
  configured: boolean;
  authenticated: boolean;
}

// Spotify connection control. The OAuth round-trip happens in a **pop-up** window
// (so the host/editor page — and its WebSocket — survive the redirect). We poll
// `/api/spotify/status` until the pop-up reports the account is linked, then close
// it. ⚠️ window.open must stay inside the click handler or pop-up blockers kill it.
export default function SpotifyConnect({
  onAuthenticated,
  className = "",
}: {
  onAuthenticated?: () => void;
  className?: string;
}) {
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wasAuthedRef = useRef(false);

  const refresh = useCallback(async (): Promise<boolean> => {
    try {
      const r = await fetch(backendHttpUrl("/api/spotify/status"));
      const d = (await r.json()) as SpotifyStatus;
      setStatus(d);
      if (d.authenticated && !wasAuthedRef.current) {
        wasAuthedRef.current = true;
        onAuthenticated?.();
      }
      return d.authenticated;
    } catch {
      setError("Impossible de contacter le serveur.");
      return false;
    }
  }, [onAuthenticated]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  function connect() {
    setError(null);
    const url = backendHttpUrl(`/auth/spotify/login?return_to=${encodeURIComponent("/spotify-connected")}`);
    const popup = window.open(url, "boucan-spotify", "width=480,height=720");
    if (!popup) {
      setError("Pop-up bloquée — autorise les pop-ups pour ce site.");
      return;
    }
    setConnecting(true);
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const ok = await refresh();
      if (ok) {
        if (pollRef.current) clearInterval(pollRef.current);
        setConnecting(false);
        try { popup.close(); } catch { /* cross-origin while loading — ignore */ }
      } else if (popup.closed) {
        if (pollRef.current) clearInterval(pollRef.current);
        setConnecting(false);
      }
    }, 1500);
  }

  return (
    <div className={`rounded-xl border border-panel2 bg-ink/30 px-4 py-3 ${className}`}>
      {error ? (
        <p className="font-mono text-sm text-buzz">{error}</p>
      ) : status === null ? (
        <p className="font-mono text-sm text-muted">Vérification Spotify…</p>
      ) : !status.configured ? (
        <p className="font-mono text-sm text-muted">Variables Spotify manquantes côté serveur (.env)</p>
      ) : status.authenticated ? (
        <p className="font-mono text-sm text-volt">Spotify connecté ✓</p>
      ) : (
        <div className="flex items-center gap-3">
          <Button variant="accent" onClick={connect} disabled={connecting}>
            {connecting ? "Connexion…" : "Connecter Spotify"}
          </Button>
          {connecting && <span className="font-mono text-xs text-muted">Termine la connexion dans la fenêtre Spotify…</span>}
        </div>
      )}
    </div>
  );
}
