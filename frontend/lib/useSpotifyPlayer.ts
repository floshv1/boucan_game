"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Backend HTTP URL helper — mirrors backendWsUrl() in useGameSocket.ts.
// The page is served on :3200 but the backend API lives on :8200.
// ---------------------------------------------------------------------------
function backendHttpUrl(path: string): string {
  const proto = window.location.protocol; // "http:" or "https:"
  const port = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8200";
  return `${proto}//${window.location.hostname}:${port}${path}`;
}

// ---------------------------------------------------------------------------
// Token helper — fetches a fresh Spotify access token from the backend.
// ---------------------------------------------------------------------------
async function fetchSpotifyToken(): Promise<string> {
  const url = backendHttpUrl("/api/spotify/token");
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Token fetch failed: ${res.status}`);
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------
export interface SpotifyPlayerControls {
  ready: boolean;
  deviceId: string | null;
  error: string | null;
  play: (uri: string, startMs: number) => void;
  pause: () => void;
  resume: () => void;
  seek: (ms: number) => void;
  volume: number;
  setVolume: (v: number) => void;
}

// ---------------------------------------------------------------------------
// useSpotifyPlayer — host-only hook that drives the Spotify Web Playback SDK.
//
// IMPORTANT: This hook cannot be fully tested without live Spotify Premium
// credentials. All browser-global accesses are guarded with
// `typeof window !== "undefined"` so the module is SSR/build-safe.
// ---------------------------------------------------------------------------
export function useSpotifyPlayer(enabled: boolean): SpotifyPlayerControls {
  const [ready, setReady] = useState(false);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolumeState] = useState(0.8);
  const volumeRef = useRef(0.8);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const playerRef = useRef<any>(null);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let cancelled = false;

    function initPlayer() {
      if (cancelled) return;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SpotifySDK = (window as Window).Spotify;
      if (!SpotifySDK) return;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const player = new SpotifySDK.Player({
        name: "Boucan",
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        getOAuthToken: (cb: (token: string) => void) => {
          fetchSpotifyToken()
            .then((token) => cb(token))
            .catch(() => {
              /* token fetch failed — SDK will retry */
            });
        },
        volume: volumeRef.current,
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      player.addListener("ready", ({ device_id }: { device_id: string }) => {
        if (!cancelled) {
          setDeviceId(device_id);
          setReady(true);
          setError(null);
          // Re-apply volume in case the SDK reset it on reconnect.
          player.setVolume(volumeRef.current).catch(() => {/* best-effort */});
        }
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      player.addListener("not_ready", (_ev: any) => {
        if (!cancelled) setReady(false);
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      player.addListener("initialization_error", ({ message }: { message: string }) => {
        if (!cancelled) setError(`Initialization error: ${message}`);
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      player.addListener("authentication_error", ({ message }: { message: string }) => {
        if (!cancelled) setError(`Authentication error: ${message}`);
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      player.addListener("account_error", ({ message }: { message: string }) => {
        if (!cancelled) setError(`Account error: ${message}`);
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      player.addListener("playback_error", ({ message }: { message: string }) => {
        if (!cancelled) setError(`Playback error: ${message}`);
      });

      player.connect();
      playerRef.current = player;
    }

    // Inject the SDK script exactly once.
    const SCRIPT_ID = "spotify-player-sdk";
    if (!document.getElementById(SCRIPT_ID)) {
      const script = document.createElement("script");
      script.id = SCRIPT_ID;
      script.src = "https://sdk.scdn.co/spotify-player.js";
      script.async = true;
      document.body.appendChild(script);
    }

    // The SDK calls this global callback when it has loaded.
    window.onSpotifyWebPlaybackSDKReady = initPlayer;

    // If the SDK was already loaded (e.g. hot-reload), call initPlayer immediately.
    if ((window as Window).Spotify) {
      initPlayer();
    }

    return () => {
      cancelled = true;
      if (playerRef.current) {
        playerRef.current.disconnect();
        playerRef.current = null;
      }
      setReady(false);
      setDeviceId(null);
    };
  }, [enabled]);

  const play = useCallback(
    (uri: string, startMs: number) => {
      if (typeof window === "undefined") return;
      const id = deviceId;
      if (!id) return;
      const url = `https://api.spotify.com/v1/me/player/play?device_id=${encodeURIComponent(id)}`;
      const attempt = async (canRetry: boolean): Promise<void> => {
        const token = await fetchSpotifyToken();
        const res = await fetch(url, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ uris: [uri], position_ms: startMs }),
        });
        if (res.ok || res.status === 204) {
          setError(null);
          return;
        }
        // The SDK device often isn't propagated to Spotify's backend the instant
        // it registers — a first play can 404 "Device not found". Wait + retry once.
        if (res.status === 404 && canRetry) {
          await new Promise((r) => setTimeout(r, 800));
          return attempt(false);
        }
        const body = await res.text().catch(() => "");
        throw new Error(`${res.status} ${body.slice(0, 140)}`);
      };
      attempt(true).catch((err: unknown) => {
        setError(`Lecture: ${err instanceof Error ? err.message : String(err)}`);
      });
    },
    [deviceId]
  );

  const pause = useCallback(() => {
    playerRef.current?.pause();
  }, []);

  const resume = useCallback(() => {
    playerRef.current?.resume();
  }, []);

  const seek = useCallback((ms: number) => {
    playerRef.current?.seek(ms);
  }, []);

  const setVolume = useCallback((v: number) => {
    const clamped = Math.min(1, Math.max(0, v));
    volumeRef.current = clamped;
    setVolumeState(clamped);
    playerRef.current?.setVolume(clamped).catch(() => {/* best-effort */});
  }, []);

  return { ready, deviceId, error, play, pause, resume, seek, volume, setVolume };
}
