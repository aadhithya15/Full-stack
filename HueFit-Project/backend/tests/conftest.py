"""Shared test configuration.

CRITICAL: tests must be hermetic - they must never call real AI providers
or depend on what's in the developer's .env. This fixture forces the AI
keys back to placeholders for every test, so:
  - mock mode is always ON in tests (fast, free, deterministic),
  - your real Gemini/Groq quota is never touched by `pytest`.

Tests that specifically exercise the real-AI plumbing (tests/test_real_ai.py)
patch Config themselves with fake keys AND mock the HTTP calls, so they
still never hit the network.
"""
import pytest

from app.config import Config
from app.middleware.rate_limit import reset_limits


@pytest.fixture(autouse=True)
def _force_ai_placeholders(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "PLACEHOLDER_REPLACE_WHEN_AVAILABLE")
    monkeypatch.setattr(Config, "GROQ_API_KEY", "PLACEHOLDER_REPLACE_WHEN_AVAILABLE")
    yield


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Rate-limit counters are process-global - reset per test so earlier
    tests can never trip the limits for later ones."""
    reset_limits()
    yield
    reset_limits()
