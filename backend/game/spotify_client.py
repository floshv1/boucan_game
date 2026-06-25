"""Spotify Web API client — OAuth Authorization Code flow, in-memory token store.

All tokens are lost on restart; the host must re-authenticate (cahier §15 — no DB).
HTTP functions accept an optional ``client: httpx.Client`` so tests can inject a
``httpx.MockTransport``-backed client without touching the network.
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse

import httpx
from loguru import logger

# --------------------------------------------------------------------------- #
# Config helpers
# --------------------------------------------------------------------------- #

# The Web Playback SDK authenticates the user and verifies Premium during
# connect; that requires user-read-email + user-read-private in addition to
# streaming. Without them the SDK fails with "Authentication failed" even though
# the token is valid for Web API calls.
SPOTIFY_SCOPES = (
    "streaming user-read-email user-read-private "
    "user-read-playback-state user-modify-playback-state playlist-read-private"
)
_ACCOUNTS_BASE = "https://accounts.spotify.com"
_API_BASE = "https://api.spotify.com"


def _client_id() -> str:
    return os.environ.get("SPOTIFY_CLIENT_ID", "")


def _client_secret() -> str:
    return os.environ.get("SPOTIFY_CLIENT_SECRET", "")


def _redirect_uri() -> str:
    return os.environ.get("SPOTIFY_REDIRECT_URI", "")


def is_configured() -> bool:
    """Return True when all three required env vars are present."""
    return bool(_client_id() and _client_secret() and _redirect_uri())


# --------------------------------------------------------------------------- #
# In-memory token store
# --------------------------------------------------------------------------- #


@dataclass
class _TokenStore:
    access_token: str | None = field(default=None)
    refresh_token: str | None = field(default=None)
    expires_at: int = field(default=0)  # epoch ms


_store = _TokenStore()


def reset() -> None:
    """Clear all stored tokens. Call this between tests."""
    _store.access_token = None
    _store.refresh_token = None
    _store.expires_at = 0


def is_authenticated() -> bool:
    """Return True when a refresh_token is stored (we can always re-acquire access)."""
    return _store.refresh_token is not None


# --------------------------------------------------------------------------- #
# OAuth helpers
# --------------------------------------------------------------------------- #


def build_authorize_url(state: str) -> str:
    """Build the Spotify authorization URL for the Authorization Code flow.

    ``show_dialog=true`` forces Spotify to re-display the consent screen even when
    the user already authorized this app (e.g. for another integration). Without
    it Spotify can reuse an older consent that lacks the ``streaming`` scope, and
    the Web Playback SDK then fails with "Authentication failed".
    """
    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "redirect_uri": _redirect_uri(),
        "scope": SPOTIFY_SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return f"{_ACCOUNTS_BASE}/authorize?{urlencode(params)}"


def _basic_auth_header() -> str:
    raw = f"{_client_id()}:{_client_secret()}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _default_client() -> httpx.Client:
    return httpx.Client()


def exchange_code(code: str, *, client: httpx.Client | None = None) -> None:
    """Exchange an authorization code for access + refresh tokens."""
    c = client or _default_client()
    resp = c.post(
        f"{_ACCOUNTS_BASE}/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(),
        },
        headers={"Authorization": _basic_auth_header()},
    )
    resp.raise_for_status()
    body = resp.json()
    _store.access_token = body["access_token"]
    _store.refresh_token = body["refresh_token"]
    _store.expires_at = int(time.time() * 1000) + body["expires_in"] * 1000
    logger.info(
        "Spotify: code exchanged, expires in {}s, scopes granted: {}",
        body["expires_in"],
        body.get("scope", "?"),
    )


def refresh_access_token(*, client: httpx.Client | None = None) -> None:
    """Refresh the access token using the stored refresh token."""
    if not _store.refresh_token:
        raise RuntimeError("No refresh_token stored — user must authenticate first.")
    c = client or _default_client()
    resp = c.post(
        f"{_ACCOUNTS_BASE}/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": _store.refresh_token,
        },
        headers={"Authorization": _basic_auth_header()},
    )
    resp.raise_for_status()
    body = resp.json()
    _store.access_token = body["access_token"]
    # Spotify may or may not return a new refresh_token; keep the old one if absent.
    if "refresh_token" in body:
        _store.refresh_token = body["refresh_token"]
    _store.expires_at = int(time.time() * 1000) + body["expires_in"] * 1000
    logger.debug("Spotify: access token refreshed")


def get_access_token(*, client: httpx.Client | None = None) -> str:
    """Return a valid access token, refreshing proactively if it expires within 30 s."""
    if not is_authenticated():
        raise RuntimeError("Not authenticated with Spotify — call /auth/spotify/login first.")
    now_ms = int(time.time() * 1000)
    if now_ms >= _store.expires_at - 30_000:
        refresh_access_token(client=client)
    assert _store.access_token is not None  # refresh_access_token always sets it
    return _store.access_token


# --------------------------------------------------------------------------- #
# Parsing helpers (pure — no HTTP, directly unit-testable)
# --------------------------------------------------------------------------- #


def _parse_playlist_id(url: str) -> str:
    """Extract the Spotify playlist id from a URL, URI, or bare id.

    Accepts:
    - ``https://open.spotify.com/playlist/<id>?...``
    - ``spotify:playlist:<id>``
    - A bare 22-character Base62 id
    """
    url = url.strip()
    if url.startswith("https://"):
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        # path is like /playlist/<id>
        if len(parts) == 2 and parts[0] == "playlist" and parts[1]:
            return parts[1]
        raise ValueError(f"Cannot extract playlist id from URL: {url!r}")
    if url.startswith("spotify:playlist:"):
        pid = url[len("spotify:playlist:") :]
        if pid:
            return pid
        raise ValueError(f"Empty playlist id in URI: {url!r}")
    # Bare id: non-empty, no slashes/colons, looks like a Base62 string
    if url and "/" not in url and ":" not in url:
        return url
    raise ValueError(f"Cannot parse playlist id: {url!r}")


def _map_track(track: dict) -> dict:
    """Map a Spotify track object to our internal shape.

    Returns ``{spotify_track_id, uri, title, artist, cover_url, duration_ms}``.
    Defensive against missing fields (some restricted-mode responses omit them).
    """
    artists = ", ".join(a.get("name", "") for a in track.get("artists", []) if a)
    album = track.get("album") or {}
    images = album.get("images") or []
    cover_url = images[0]["url"] if images else ""
    return {
        "spotify_track_id": track.get("id", ""),
        "uri": track.get("uri", ""),
        "title": track.get("name", ""),
        "artist": artists,
        "cover_url": cover_url,
        "duration_ms": track.get("duration_ms", 0),
    }


# --------------------------------------------------------------------------- #
# API calls
# --------------------------------------------------------------------------- #

_PLAYLIST_CAP = 100  # max tracks imported from a playlist


def _extract_playlist_items(body: dict) -> list[dict]:
    """Pull the list of playlist-item wrappers from a playlist-object response.

    Handles two shapes returned by Spotify:
    - standard: tracks paging under ``body["tracks"]``, track under ``item["track"]``
    - partner/restricted: paging under top-level ``body["items"]``, track under ``item["item"]``
    """
    paging = body.get("tracks") or body.get("items") or {}
    if not isinstance(paging, dict):
        return []
    return paging.get("items", []) or []


def import_playlist(url: str, *, client: httpx.Client | None = None) -> dict:
    """Fetch a Spotify playlist URL/URI/id and return its metadata + mapped tracks.

    Reads the playlist *object* endpoint (``/v1/playlists/{id}``) rather than the
    dedicated ``/tracks`` sub-resource: the latter is blocked (403) for apps in
    Spotify Development Mode, while the object embeds the first page of tracks.
    Caps at ``_PLAYLIST_CAP`` tracks; skips null or local tracks.

    Returns ``{"name", "external_url", "track_count", "tracks"}``. ``track_count``
    is the playlist's full total (from Spotify), which may exceed ``len(tracks)``
    when the playlist is larger than ``_PLAYLIST_CAP``.
    """
    playlist_id = _parse_playlist_id(url)
    access_token = get_access_token(client=client)
    c = client or _default_client()
    headers = {"Authorization": f"Bearer {access_token}"}

    resp = c.get(f"{_API_BASE}/v1/playlists/{playlist_id}", headers=headers)
    resp.raise_for_status()
    body = resp.json()

    tracks: list[dict] = []
    for item in _extract_playlist_items(body):
        track = item.get("track") or item.get("item")
        # Skip null tracks and local files (no Spotify id)
        if not track or not track.get("id"):
            continue
        tracks.append(_map_track(track))
        if len(tracks) >= _PLAYLIST_CAP:
            break

    paging = body.get("tracks") if isinstance(body.get("tracks"), dict) else {}
    total = paging.get("total")
    meta = {
        "name": body.get("name") or "Playlist",
        "external_url": (body.get("external_urls") or {}).get("spotify"),
        "track_count": int(total) if isinstance(total, int) else len(tracks),
        "tracks": tracks,
    }
    logger.info("Spotify: imported {} tracks from playlist {} ({})", len(tracks), playlist_id, meta["name"])
    return meta


# Spotify caps the search ``limit`` at 10 for apps in Development Mode
# (higher values return 400 "Invalid limit").
_SEARCH_LIMIT = 10


def search_tracks(q: str, *, limit: int = _SEARCH_LIMIT, client: httpx.Client | None = None) -> list[dict]:
    """Search Spotify for tracks matching ``q`` and return mapped dicts."""
    access_token = get_access_token(client=client)
    c = client or _default_client()
    resp = c.get(
        f"{_API_BASE}/v1/search",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"q": q, "type": "track", "limit": min(max(1, limit), _SEARCH_LIMIT)},
    )
    resp.raise_for_status()
    body = resp.json()
    items = body.get("tracks", {}).get("items", [])
    return [_map_track(t) for t in items]
