"use client";

import { Dispatch, SetStateAction, useEffect, useState } from "react";

import BonusToggle from "@/components/BonusToggle";
import { backendHttpUrl } from "@/lib/backend";
import { BlindtestTrackDraft } from "@/lib/types";

interface Props {
  tracks: BlindtestTrackDraft[];
  setTracks: Dispatch<SetStateAction<BlindtestTrackDraft[]>>;
  // Path the Spotify OAuth round-trip returns to (e.g. "/host/ABC" or "/editor/<id>").
  returnTo: string;
}

interface SpotifyStatus {
  configured: boolean;
  authenticated: boolean;
}

interface ApiTrack {
  spotify_track_id: string;
  uri: string;
  title: string;
  artist: string;
  cover_url: string;
  duration_ms: number;
}

function trackFromApi(t: ApiTrack): BlindtestTrackDraft {
  return { ...t, start_ms: 0, points_title: 1, points_artist: 1 };
}

export default function BlindtestEditor({ tracks, setTracks, returnTo }: Props) {
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [playlistUrl, setPlaylistUrl] = useState("");
  const [playlistLoading, setPlaylistLoading] = useState(false);
  const [playlistError, setPlaylistError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<ApiTrack[]>([]);

  // Fetch Spotify connection status on mount.
  useEffect(() => {
    fetch(backendHttpUrl("/api/spotify/status"))
      .then((r) => r.json())
      .then((d: SpotifyStatus) => setStatus(d))
      .catch(() => setStatusError("Impossible de contacter le serveur."));
  }, []);

  function connectSpotify() {
    const target = encodeURIComponent(returnTo);
    window.location.href = backendHttpUrl(`/auth/spotify/login?return_to=${target}`);
  }

  async function importPlaylist() {
    if (!playlistUrl.trim()) return;
    setPlaylistLoading(true);
    setPlaylistError(null);
    try {
      const res = await fetch(
        backendHttpUrl(`/api/spotify/playlist?url=${encodeURIComponent(playlistUrl.trim())}`),
      );
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setPlaylistError(body.error ?? `Erreur ${res.status}`);
        return;
      }
      const data = (await res.json()) as { tracks: ApiTrack[] };
      setTracks((prev) => [...prev, ...data.tracks.map(trackFromApi)]);
      setPlaylistUrl("");
    } catch {
      setPlaylistError("Erreur réseau.");
    } finally {
      setPlaylistLoading(false);
    }
  }

  async function searchTracks() {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await fetch(
        backendHttpUrl(`/api/spotify/search?q=${encodeURIComponent(searchQuery.trim())}`),
      );
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setSearchError(body.error ?? `Erreur ${res.status}`);
        return;
      }
      const data = (await res.json()) as { tracks: ApiTrack[] };
      setSearchResults(data.tracks);
    } catch {
      setSearchError("Erreur réseau.");
    } finally {
      setSearchLoading(false);
    }
  }

  function addTrack(t: ApiTrack) {
    setTracks((prev) => [...prev, trackFromApi(t)]);
  }

  function removeTrack(i: number) {
    setTracks((prev) => prev.filter((_, j) => j !== i));
  }

  function patchTrack(i: number, patch: Partial<BlindtestTrackDraft>) {
    setTracks((prev) => prev.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Spotify connection status */}
      <div className="rounded-xl border border-panel2 bg-ink/30 px-4 py-3">
        {statusError ? (
          <p className="font-mono text-sm text-buzz">{statusError}</p>
        ) : status === null ? (
          <p className="font-mono text-sm text-muted">Vérification Spotify…</p>
        ) : !status.configured ? (
          <p className="font-mono text-sm text-muted">
            Variables Spotify manquantes côté serveur (.env)
          </p>
        ) : !status.authenticated ? (
          <button
            onClick={connectSpotify}
            className="rounded-xl bg-buzz px-4 py-3 font-display text-lg text-white shadow-[0_8px_0_0_#8e0c22] transition active:translate-y-1 active:shadow-[0_3px_0_0_#8e0c22]"
          >
            Connecter Spotify
          </button>
        ) : (
          <p className="font-mono text-sm text-volt">Spotify connecté ✓</p>
        )}
      </div>

      {/* Import playlist */}
      <div className="flex flex-col gap-2">
        <label className="font-mono text-xs uppercase tracking-widest text-muted">
          Importer une playlist
        </label>
        <div className="flex gap-2">
          <input
            value={playlistUrl}
            onChange={(e) => setPlaylistUrl(e.target.value)}
            placeholder="URL Spotify de la playlist"
            className="flex-1 rounded-lg border border-panel2 bg-ink/60 px-3 py-2 outline-none placeholder:text-muted focus:border-muted"
          />
          <button
            onClick={importPlaylist}
            disabled={playlistLoading || !playlistUrl.trim()}
            className="rounded-xl border border-panel2 px-4 py-2 font-display text-lg hover:border-muted disabled:opacity-40"
          >
            {playlistLoading ? "…" : "Importer"}
          </button>
        </div>
        {playlistError && <p className="font-mono text-xs text-buzz">{playlistError}</p>}
      </div>

      {/* Search */}
      <div className="flex flex-col gap-2">
        <label className="font-mono text-xs uppercase tracking-widest text-muted">
          Rechercher un morceau
        </label>
        <div className="flex gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && searchTracks()}
            placeholder="Titre, artiste…"
            className="flex-1 rounded-lg border border-panel2 bg-ink/60 px-3 py-2 outline-none placeholder:text-muted focus:border-muted"
          />
          <button
            onClick={searchTracks}
            disabled={searchLoading || !searchQuery.trim()}
            className="rounded-xl border border-panel2 px-4 py-2 font-display text-lg hover:border-muted disabled:opacity-40"
          >
            {searchLoading ? "…" : "Rechercher"}
          </button>
        </div>
        {searchError && <p className="font-mono text-xs text-buzz">{searchError}</p>}
        {searchResults.length > 0 && (
          <ul className="flex flex-col gap-1.5 rounded-xl border border-panel2 bg-ink/20 p-3">
            {searchResults.map((t) => (
              <li key={t.spotify_track_id} className="flex items-center gap-3">
                {t.cover_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={t.cover_url} alt="" className="h-8 w-8 rounded object-cover" />
                )}
                <span className="flex-1 truncate text-sm">
                  {t.title} — <span className="text-muted">{t.artist}</span>
                </span>
                <button
                  onClick={() => addTrack(t)}
                  className="rounded-lg border border-panel2 px-2 py-1 font-mono text-xs hover:border-muted hover:text-cream"
                >
                  + Ajouter
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Track list */}
      {tracks.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="font-mono text-xs uppercase tracking-widest text-muted">
            Morceaux ({tracks.length})
          </span>
          {tracks.map((t, i) => (
            <div key={i} className="rounded-xl border border-panel2 bg-ink/40 p-3">
              <div className="mb-2 flex items-center gap-3">
                {t.cover_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={t.cover_url} alt="" className="h-10 w-10 rounded object-cover" />
                )}
                <span className="flex-1 truncate text-sm font-medium">
                  {t.title}{" "}
                  <span className="text-muted">— {t.artist}</span>
                </span>
                <button
                  onClick={() => removeTrack(i)}
                  className="font-mono text-xs text-muted hover:text-buzz"
                >
                  retirer ✕
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-3 font-mono text-xs text-muted">
                <label className="flex items-center gap-1.5">
                  Départ (s)
                  <input
                    type="number"
                    min={0}
                    value={Math.round(t.start_ms / 1000)}
                    onChange={(e) =>
                      patchTrack(i, { start_ms: (Number.parseInt(e.target.value, 10) || 0) * 1000 })
                    }
                    className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
                  />
                </label>
                <BonusToggle on={!!t.bonus} onChange={(v) => patchTrack(i, { bonus: v })} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
