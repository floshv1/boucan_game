"""Shared test fixtures."""

from __future__ import annotations

import pytest
from loguru import logger

from game import engine


@pytest.fixture(autouse=True, scope="session")
def _quiet_logs():
    """Drop loguru sinks for the test session. Logging to stderr from the
    Starlette TestClient's worker thread (under pytest capture) intermittently
    deadlocks the anyio portal — and tests don't need the output anyway."""
    logger.remove()
    yield


@pytest.fixture(autouse=True)
def _no_reading_delay():
    """Disable the question reading window during tests so flows are instantaneous
    and deterministic. Referenced via the module attribute so engine/qcm/main all
    see the override. Tests that specifically exercise the reading window set it
    explicitly."""
    original = engine.READING_MS
    engine.READING_MS = 0
    yield
    engine.READING_MS = original
