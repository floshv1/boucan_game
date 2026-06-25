"""HTTP endpoints for Spotify OAuth and API proxy.

The router is NOT yet mounted in main.py (that happens in a later task).
State/CSRF map is in-memory and resets on restart — acceptable for a home server.
"""

from __future__ import annotations

import os
import secrets

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger

from game import spotify_client

router = APIRouter()

# In-memory CSRF / return-to map: state_token → return_to path
_pending_states: dict[str, str] = {}

_DEFAULT_FRONTEND_URL = "http://localhost:3200"


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", _DEFAULT_FRONTEND_URL).rstrip("/")


def _safe_return_to(value: str) -> str:
    """Validate that return_to is a relative path starting with '/'.

    Falls back to '/' if the value is invalid to avoid open-redirect.
    """
    if value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


# --------------------------------------------------------------------------- #
# OAuth
# --------------------------------------------------------------------------- #


@router.get("/auth/spotify/login", response_model=None)
async def spotify_login(return_to: str = "/") -> RedirectResponse | JSONResponse:
    """Redirect to Spotify's authorization page.

    Returns 503 if the required env vars are not set.
    """
    if not spotify_client.is_configured():
        return JSONResponse(
            status_code=503,
            content={
                "error": "spotify_not_configured",
                "detail": (
                    "Missing one or more Spotify env vars: "
                    "SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI."
                ),
            },
        )
    state = secrets.token_urlsafe(16)
    _pending_states[state] = _safe_return_to(return_to)
    url = spotify_client.build_authorize_url(state)
    logger.info("Spotify login: redirecting to Spotify (state={})", state)
    return RedirectResponse(url=url)


@router.get("/auth/spotify/callback", response_model=None)
async def spotify_callback(
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    """Handle the OAuth callback from Spotify.

    On success: redirects to ``FRONTEND_URL + return_to + ?spotify=connected``.
    On failure: redirects to ``FRONTEND_URL + return_to + ?spotify=error``.
    """
    return_to = _pending_states.pop(state, None)
    frontend = _frontend_url()

    if error or return_to is None:
        # Unknown state (possible CSRF) or Spotify returned an error.
        fallback = return_to or "/"
        logger.warning("Spotify callback error: error={!r} known_state={}", error, return_to is not None)
        return RedirectResponse(url=f"{frontend}{fallback}?spotify=error")

    try:
        spotify_client.exchange_code(code)
    except Exception as exc:
        logger.error("Spotify code exchange failed: {}", exc)
        return RedirectResponse(url=f"{frontend}{return_to}?spotify=error")

    logger.info("Spotify: authenticated successfully, redirecting to {}", return_to)
    return RedirectResponse(url=f"{frontend}{return_to}?spotify=connected")


# --------------------------------------------------------------------------- #
# Status / token
# --------------------------------------------------------------------------- #


@router.get("/api/spotify/status")
async def spotify_status() -> dict:
    """Return whether Spotify integration is configured and authenticated."""
    return {
        "configured": spotify_client.is_configured(),
        "authenticated": spotify_client.is_authenticated(),
    }


@router.get("/api/spotify/token", response_model=None)
async def spotify_token() -> dict | JSONResponse:
    """Return the current access token.

    Returns 401 if not authenticated.
    """
    if not spotify_client.is_authenticated():
        return JSONResponse(
            status_code=401,
            content={"error": "not_authenticated", "detail": "Not authenticated with Spotify."},
        )
    try:
        token = spotify_client.get_access_token()
    except RuntimeError as exc:
        return JSONResponse(status_code=401, content={"error": "not_authenticated", "detail": str(exc)})
    return {"access_token": token}


# --------------------------------------------------------------------------- #
# Playlist / search
# --------------------------------------------------------------------------- #


@router.get("/api/spotify/playlist", response_model=None)
async def spotify_playlist(url: str) -> dict | JSONResponse:
    """Import tracks from a Spotify playlist URL/URI/id.

    Returns 400 on a bad URL, 401 if not authenticated.
    """
    if not spotify_client.is_authenticated():
        return JSONResponse(
            status_code=401,
            content={"error": "not_authenticated", "detail": "Not authenticated with Spotify."},
        )
    try:
        tracks = spotify_client.import_playlist(url)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "bad_url", "detail": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=401, content={"error": "not_authenticated", "detail": str(exc)})
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": "spotify_error", "detail": f"Spotify a renvoyé {exc.response.status_code}"},
        )
    return {"tracks": tracks}


@router.get("/api/spotify/search", response_model=None)
async def spotify_search(q: str) -> dict | JSONResponse:
    """Search Spotify for tracks.

    Returns 401 if not authenticated.
    """
    if not spotify_client.is_authenticated():
        return JSONResponse(
            status_code=401,
            content={"error": "not_authenticated", "detail": "Not authenticated with Spotify."},
        )
    try:
        tracks = spotify_client.search_tracks(q)
    except RuntimeError as exc:
        return JSONResponse(status_code=401, content={"error": "not_authenticated", "detail": str(exc)})
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": "spotify_error", "detail": f"Spotify a renvoyé {exc.response.status_code}"},
        )
    return {"tracks": tracks}
