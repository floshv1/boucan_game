"""Tests for game.spotify_client and routers.spotify.

All Spotify HTTP calls are stubbed with httpx.MockTransport — no real network.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from game import spotify_client
from game.store import SessionStore
from routers.spotify import router as spotify_router

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    """Wrap a handler function in an httpx.MockTransport."""
    return httpx.MockTransport(handler)


def _json_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=data)


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=_make_transport(handler))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def reset_store(monkeypatch):
    """Reset the in-memory token store and set dummy env vars before each test."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost:8200/auth/spotify/callback")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3200")
    spotify_client.reset()
    yield
    spotify_client.reset()


# --------------------------------------------------------------------------- #
# _parse_playlist_id
# --------------------------------------------------------------------------- #


def test_parse_playlist_id_open_url():
    pid = spotify_client._parse_playlist_id("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc")
    assert pid == "37i9dQZF1DXcBWIGoYBM5M"


def test_parse_playlist_id_uri():
    pid = spotify_client._parse_playlist_id("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
    assert pid == "37i9dQZF1DXcBWIGoYBM5M"


def test_parse_playlist_id_bare():
    pid = spotify_client._parse_playlist_id("37i9dQZF1DXcBWIGoYBM5M")
    assert pid == "37i9dQZF1DXcBWIGoYBM5M"


def test_parse_playlist_id_bad_url():
    with pytest.raises(ValueError):
        spotify_client._parse_playlist_id("https://open.spotify.com/track/abc")


def test_parse_playlist_id_garbage():
    with pytest.raises(ValueError):
        spotify_client._parse_playlist_id("not:a:valid:thing:here")


# --------------------------------------------------------------------------- #
# _map_track
# --------------------------------------------------------------------------- #

_SAMPLE_TRACK = {
    "id": "4uLU6hMCjMI75M1A2tKUQC",
    "uri": "spotify:track:4uLU6hMCjMI75M1A2tKUQC",
    "name": "Never Gonna Give You Up",
    "duration_ms": 213573,
    "artists": [{"name": "Rick Astley"}],
    "album": {
        "images": [{"url": "https://i.scdn.co/image/abc", "height": 640, "width": 640}],
    },
}

_SAMPLE_TRACK_MULTI_ARTIST = {
    "id": "abc123",
    "uri": "spotify:track:abc123",
    "name": "Collab Song",
    "duration_ms": 180000,
    "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
    "album": {"images": []},
}


def test_map_track_basic():
    result = spotify_client._map_track(_SAMPLE_TRACK)
    assert result == {
        "spotify_track_id": "4uLU6hMCjMI75M1A2tKUQC",
        "uri": "spotify:track:4uLU6hMCjMI75M1A2tKUQC",
        "title": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "cover_url": "https://i.scdn.co/image/abc",
        "duration_ms": 213573,
    }


def test_map_track_multiple_artists():
    result = spotify_client._map_track(_SAMPLE_TRACK_MULTI_ARTIST)
    assert result["artist"] == "Artist A, Artist B"


def test_map_track_no_images():
    result = spotify_client._map_track(_SAMPLE_TRACK_MULTI_ARTIST)
    assert result["cover_url"] == ""


# --------------------------------------------------------------------------- #
# exchange_code
# --------------------------------------------------------------------------- #


def test_exchange_code_stores_tokens():
    now_before = int(time.time() * 1000)

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/token"
        body = dict(item.split("=") for item in req.content.decode().split("&"))
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "auth_code_xyz"
        return _json_response(
            {
                "access_token": "acc_tok_1",
                "refresh_token": "ref_tok_1",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )

    spotify_client.exchange_code("auth_code_xyz", client=_make_client(handler))

    assert spotify_client._store.access_token == "acc_tok_1"
    assert spotify_client._store.refresh_token == "ref_tok_1"
    assert spotify_client._store.expires_at >= now_before + 3600 * 1000


# --------------------------------------------------------------------------- #
# refresh_access_token
# --------------------------------------------------------------------------- #


def test_refresh_access_token_updates_access_keeps_refresh():
    # Pre-populate a refresh token
    spotify_client._store.refresh_token = "ref_tok_original"
    spotify_client._store.access_token = "acc_tok_old"
    spotify_client._store.expires_at = 0

    def handler(req: httpx.Request) -> httpx.Response:
        body = dict(item.split("=") for item in req.content.decode().split("&"))
        assert body["grant_type"] == "refresh_token"
        assert body["refresh_token"] == "ref_tok_original"
        # Spotify does NOT return a new refresh_token in this response
        return _json_response({"access_token": "acc_tok_new", "expires_in": 3600, "token_type": "Bearer"})

    spotify_client.refresh_access_token(client=_make_client(handler))

    assert spotify_client._store.access_token == "acc_tok_new"
    assert spotify_client._store.refresh_token == "ref_tok_original"  # kept


def test_refresh_access_token_stores_new_refresh_when_provided():
    spotify_client._store.refresh_token = "ref_tok_original"
    spotify_client._store.access_token = "acc_tok_old"
    spotify_client._store.expires_at = 0

    def handler(req: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "access_token": "acc_tok_new",
                "refresh_token": "ref_tok_rotated",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )

    spotify_client.refresh_access_token(client=_make_client(handler))
    assert spotify_client._store.refresh_token == "ref_tok_rotated"


# --------------------------------------------------------------------------- #
# get_access_token
# --------------------------------------------------------------------------- #


def test_get_access_token_raises_when_not_authenticated():
    with pytest.raises(RuntimeError, match="Not authenticated"):
        spotify_client.get_access_token()


def test_get_access_token_returns_cached_when_valid():
    """If the token is still fresh, the transport should NOT be called."""
    spotify_client._store.access_token = "cached_token"
    spotify_client._store.refresh_token = "ref_tok"
    # Expires 10 minutes from now
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _json_response({})

    token = spotify_client.get_access_token(client=_make_client(handler))
    assert token == "cached_token"
    assert call_count == 0, "Should not have hit the network for a valid token"


def test_get_access_token_refreshes_when_expired():
    """If the token is expired (or about to expire), it should call refresh."""
    spotify_client._store.access_token = "old_token"
    spotify_client._store.refresh_token = "ref_tok"
    # Already expired
    spotify_client._store.expires_at = int(time.time() * 1000) - 1000

    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _json_response({"access_token": "new_token", "expires_in": 3600, "token_type": "Bearer"})

    token = spotify_client.get_access_token(client=_make_client(handler))
    assert token == "new_token"
    assert call_count == 1, "Should have called refresh exactly once"


# --------------------------------------------------------------------------- #
# import_playlist
# --------------------------------------------------------------------------- #

_TRACK_1 = {
    "id": "tid1",
    "uri": "spotify:track:tid1",
    "name": "Track One",
    "duration_ms": 200000,
    "artists": [{"name": "Artist One"}],
    "album": {"images": [{"url": "http://cover1.jpg"}]},
}
_TRACK_2 = {
    "id": "tid2",
    "uri": "spotify:track:tid2",
    "name": "Track Two",
    "duration_ms": 210000,
    "artists": [{"name": "Artist Two"}],
    "album": {"images": [{"url": "http://cover2.jpg"}]},
}
_TRACK_3 = {
    "id": "tid3",
    "uri": "spotify:track:tid3",
    "name": "Track Three",
    "duration_ms": 220000,
    "artists": [{"name": "Artist Three"}],
    "album": {"images": []},
}


def test_import_playlist_via_items_endpoint_skips_null():
    """Feb-2026 path: metadata from the object endpoint, tracks from /items (shape:
    items list, track under 'item'). One null track is skipped → 2 mapped tracks."""
    spotify_client._store.access_token = "acc_tok"
    spotify_client._store.refresh_token = "ref_tok"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    seen_paths = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_paths.append(req.url.path)
        if req.url.path == "/v1/playlists/PID/items":
            return _json_response(
                {
                    "total": 2,
                    "next": None,
                    "items": [{"item": _TRACK_1}, {"item": None}, {"item": _TRACK_2}],
                }
            )
        return _json_response({"name": "My BlindTest", "external_urls": {"spotify": "http://x"}})

    result = spotify_client.import_playlist("spotify:playlist:PID", client=_make_client(handler))

    assert "/v1/playlists/PID/items" in seen_paths, "must use the new /items endpoint"
    assert [t["spotify_track_id"] for t in result["tracks"]] == ["tid1", "tid2"]
    assert result["name"] == "My BlindTest"
    assert result["truncated"] is False
    assert set(result) >= {"name", "external_url", "track_count", "tracks"}


def test_import_playlist_items_follows_pagination_beyond_one_page():
    """>1 page: follow the /items 'next' cursor to import past the first 100."""
    spotify_client._store.access_token = "acc_tok"
    spotify_client._store.refresh_token = "ref_tok"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    page2 = "https://api.spotify.com/v1/playlists/PID/items?offset=100&limit=100"

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/playlists/PID":
            return _json_response({"name": "Big"})
        if str(req.url.params.get("offset")) == "100":
            return _json_response({"total": 2, "next": None, "items": [{"item": _TRACK_2}]})
        return _json_response({"total": 2, "next": page2, "items": [{"item": _TRACK_1}]})

    result = spotify_client.import_playlist("spotify:playlist:PID", client=_make_client(handler))
    assert [t["spotify_track_id"] for t in result["tracks"]] == ["tid1", "tid2"]
    assert result["truncated"] is False
    assert result["track_count"] == 2


def test_import_playlist_skips_local_tracks():
    """Tracks without an id (local files) must be skipped."""
    spotify_client._store.access_token = "acc_tok"
    spotify_client._store.refresh_token = "ref_tok"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    local_track = {
        "id": None,  # local file has no id
        "uri": "spotify:local:...",
        "name": "Local File",
        "duration_ms": 0,
        "artists": [],
        "album": {"images": []},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/items":
            return _json_response({"total": 1, "next": None, "items": [{"item": local_track}, {"item": _TRACK_1}]})
        return _json_response({"name": "P"})

    result = spotify_client.import_playlist("37i9dQZF1DXcBWIGoYBM5M", client=_make_client(handler))
    assert len(result["tracks"]) == 1
    assert result["tracks"][0]["spotify_track_id"] == "tid1"


def test_import_playlist_falls_back_to_embedded_when_items_forbidden():
    """If /items is unusable for this playlist (401/403, e.g. not owned), fall back to
    the object endpoint's embedded first page and flag truncated."""
    spotify_client._store.access_token = "acc_tok"
    spotify_client._store.refresh_token = "ref_tok"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/playlists/PID/items":
            return _json_response({"error": {"status": 403}}, status_code=403)
        return _json_response(
            {"name": "Big", "tracks": {"items": [{"track": _TRACK_1}], "total": 200}}
        )

    result = spotify_client.import_playlist("spotify:playlist:PID", client=_make_client(handler))
    assert [t["spotify_track_id"] for t in result["tracks"]] == ["tid1"]
    assert result["truncated"] is True
    assert result["track_count"] == 200


# --------------------------------------------------------------------------- #
# search_tracks
# --------------------------------------------------------------------------- #


def test_search_tracks_maps_items():
    spotify_client._store.access_token = "acc_tok"
    spotify_client._store.refresh_token = "ref_tok"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    def handler(req: httpx.Request) -> httpx.Response:
        assert "search" in str(req.url)
        assert req.url.params["q"] == "rick astley"
        assert req.url.params["type"] == "track"
        # Spotify dev-mode caps limit at 10; we must never request more.
        assert int(req.url.params["limit"]) <= 10
        return _json_response({"tracks": {"items": [_TRACK_1, _TRACK_2]}})

    results = spotify_client.search_tracks("rick astley", limit=50, client=_make_client(handler))
    assert len(results) == 2
    assert results[0]["title"] == "Track One"
    assert results[1]["title"] == "Track Two"


# --------------------------------------------------------------------------- #
# Router tests (TestClient — offline, router mounted on bare FastAPI app)
# --------------------------------------------------------------------------- #


@pytest.fixture()
def test_app():
    app = FastAPI()
    app.include_router(spotify_router)
    # The token endpoint is gated to a live host; give the app a store with one
    # session so tests can present a valid host_secret.
    app.state.store = SessionStore()
    app.state.store.create()
    return app


def _host_secret(test_app) -> str:
    return next(iter(test_app.state.store._sessions.values())).host_secret


@pytest.fixture()
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=False)


def test_status_shape(client):
    resp = client.get("/api/spotify/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "configured" in body
    assert "authenticated" in body
    assert isinstance(body["configured"], bool)
    assert isinstance(body["authenticated"], bool)


def test_token_403_without_host_secret(client):
    # No (or wrong) host_secret → forbidden, before any Spotify check.
    assert client.get("/api/spotify/token").status_code == 403
    assert client.get("/api/spotify/token", params={"host_secret": "nope"}).status_code == 403


def test_token_401_when_unauthenticated(client, test_app):
    # Valid host gets past the gate; store is reset by autouse fixture → no tokens.
    resp = client.get("/api/spotify/token", params={"host_secret": _host_secret(test_app)})
    assert resp.status_code == 401


def test_token_returns_token_for_host_when_authenticated(client, test_app):
    spotify_client._store.access_token = "acc_tok"
    spotify_client._store.refresh_token = "ref_tok"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000
    resp = client.get("/api/spotify/token", params={"host_secret": _host_secret(test_app)})
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "acc_tok"


def test_login_redirects_to_spotify(client):
    # is_configured() reads env — the autouse fixture set them
    resp = client.get("/auth/spotify/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "accounts.spotify.com/authorize" in location
    assert "client_id=test_client_id" in location


def test_login_503_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    resp = client.get("/auth/spotify/login")
    assert resp.status_code == 503
    assert resp.json()["error"] == "spotify_not_configured"


def test_playlist_401_when_unauthenticated(client):
    resp = client.get("/api/spotify/playlist", params={"url": "spotify:playlist:abc"})
    assert resp.status_code == 401


def test_playlist_400_on_bad_url(client):
    # Authenticate first so we get past the auth check
    spotify_client._store.refresh_token = "ref"
    spotify_client._store.access_token = "acc"
    spotify_client._store.expires_at = int(time.time() * 1000) + 600_000

    resp = client.get("/api/spotify/playlist", params={"url": "not:a:valid:url"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "bad_url"


def test_search_401_when_unauthenticated(client):
    resp = client.get("/api/spotify/search", params={"q": "hello"})
    assert resp.status_code == 401


def test_build_authorize_url_contains_all_params():
    url = spotify_client.build_authorize_url("mystate123")
    assert "response_type=code" in url
    assert "client_id=test_client_id" in url
    assert "state=mystate123" in url
    assert "scope=" in url
    assert "redirect_uri=" in url
