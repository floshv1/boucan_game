"""HTTP endpoints for session creation / lookup.

Session creation returns the ``host_secret`` exactly once — only the holder can
later authenticate as host over the WebSocket (cahier §16).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/sessions")
async def create_session(request: Request) -> dict:
    session = request.app.state.store.create()
    return {"code": session.code, "host_secret": session.host_secret}


@router.get("/sessions/{code}")
async def get_session(code: str, request: Request) -> dict:
    session = request.app.state.store.get(code)
    return {"exists": session is not None, "code": code.upper()}
