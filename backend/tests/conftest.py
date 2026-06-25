"""Shared test fixtures."""

from __future__ import annotations

import pytest

from game import engine


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
