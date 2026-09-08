"""Lightweight in-memory rate limiter (no extra dependencies).

Usage:
    @fashion_bp.post("/analyze")
    @require_auth
    @rate_limit("analyze", per_minute=10)     # keyed by user id (after auth)
    def analyze(): ...

    @auth_bp.post("/login")
    @rate_limit("login", per_minute=5)        # keyed by client IP (no auth yet)
    def login(): ...

Sliding-window counter per (rule, key). Kept in process memory - perfect
for a single Render instance; if the app ever scales to multiple workers,
swap the store for Redis behind the same decorator.

Returns the unified 429 RATE_LIMITED error when exceeded.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from functools import wraps
from threading import Lock

from flask import g, request

from app.utils.errors import ApiError

_WINDOW = 60.0  # seconds
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = Lock()


def _client_key() -> str:
    """User id when authenticated, else client IP (proxy-aware)."""
    user = getattr(g, "user", None)
    if user and user.get("id"):
        return f"u:{user['id']}"
    fwd = request.headers.get("X-Forwarded-For", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")
    return f"ip:{ip}"


def rate_limit(rule: str, per_minute: int):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (rule, _client_key())
            now = time.monotonic()
            with _lock:
                q = _hits[key]
                while q and now - q[0] > _WINDOW:
                    q.popleft()
                if len(q) >= per_minute:
                    retry_in = int(_WINDOW - (now - q[0])) + 1
                    raise ApiError.rate_limited(
                        f"Too many requests - try again in about {retry_in} seconds"
                    )
                q.append(now)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def reset_limits() -> None:
    """Testing helper."""
    with _lock:
        _hits.clear()
