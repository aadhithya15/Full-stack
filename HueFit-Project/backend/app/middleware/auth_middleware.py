"""@require_auth decorator â€” protects endpoints with Bearer-token auth.

Usage:
    from app.middleware.auth_middleware import require_auth

    @fashion_bp.post("/analyze")
    @require_auth
    def analyze():
        user_id = g.user["id"]     # guaranteed present
        ...

On success: g.user = {"id", "email", "full_name"}.
On failure: raises 401 UNAUTHORIZED in the unified error format.
"""
from __future__ import annotations

from functools import wraps

from flask import g, request

from app.services.auth_service import get_user_from_token
from app.utils.errors import ApiError


def _extract_bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError.unauthorized("Missing Authorization header (Bearer token)")
    token = header[len("Bearer ") :].strip()
    if not token:
        raise ApiError.unauthorized("Missing Authorization header (Bearer token)")
    return token


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        g.user = get_user_from_token(token)
        g.token = token
        return fn(*args, **kwargs)

    return wrapper
