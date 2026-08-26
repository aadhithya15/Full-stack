"""Auth service â€” wraps Supabase Auth (email/password).

Token verification strategy: we call Supabase's auth.get_user(token)
instead of verifying JWT signatures locally. This works with BOTH the
new asymmetric (ECC) signing keys and the legacy HS256 secret, so it
keeps working no matter how the project's JWT settings evolve.
"""
from __future__ import annotations

from typing import Any

from supabase import create_client

from app.config import Config
from app.utils.errors import ApiError


def _fresh_client():
    """A brand-new Supabase client for auth calls.

    supabase-py stores the user's session on the client after
    sign_up/sign_in and starts sending THAT user's token instead of the
    service key. Using a throwaway client per auth call keeps the shared
    client (used for DB queries) clean, and is safe with many users at once.
    """
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)


def _friendly_auth_error(exc: Exception) -> ApiError:
    """Map Supabase auth errors to clean, safe API errors."""
    msg = str(exc).lower()
    if "already registered" in msg or "already been registered" in msg:
        return ApiError.invalid_input("An account with this email already exists")
    if "invalid login credentials" in msg or "invalid_credentials" in msg:
        return ApiError.unauthorized("Invalid email or password")
    if "password" in msg and ("weak" in msg or "at least" in msg):
        return ApiError.invalid_input("Password is too weak (min 8 characters)")
    if "rate limit" in msg or "too many" in msg:
        return ApiError.rate_limited("Too many attempts, please wait a minute")
    if "email not confirmed" in msg:
        return ApiError.unauthorized("Please confirm your email, then log in")
    # Generic fallback â€” never leak internals.
    return ApiError("AUTH_ERROR", "Authentication failed, please try again", 400)


def register(email: str, password: str, full_name: str) -> dict[str, Any]:
    """Create the user in Supabase Auth. The DB trigger auto-creates the profile row."""
    sb = _fresh_client()
    try:
        res = sb.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"full_name": full_name}},
            }
        )
    except Exception as exc:  # supabase-py raises AuthApiError etc.
        raise _friendly_auth_error(exc)

    if res.user is None:
        raise ApiError("AUTH_ERROR", "Registration failed, please try again", 400)

    # If email confirmation is ON in Supabase, session is None until confirmed.
    token = res.session.access_token if res.session else None
    return {
        "token": token,
        "user": {
            "id": res.user.id,
            "email": res.user.email,
            "full_name": full_name,
        },
        "needs_email_confirmation": res.session is None,
    }


def login(email: str, password: str) -> dict[str, Any]:
    sb = _fresh_client()
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        raise _friendly_auth_error(exc)

    if res.user is None or res.session is None:
        raise ApiError.unauthorized("Invalid email or password")

    meta = res.user.user_metadata or {}
    return {
        "token": res.session.access_token,
        "user": {
            "id": res.user.id,
            "email": res.user.email,
            "full_name": meta.get("full_name", ""),
        },
    }


def get_user_from_token(token: str) -> dict[str, Any]:
    """Validate an access token with Supabase; return the user or raise 401."""
    sb = _fresh_client()
    try:
        res = sb.auth.get_user(token)
    except Exception:
        raise ApiError.unauthorized("Your session has expired, please log in again")

    if res is None or res.user is None:
        raise ApiError.unauthorized("Your session has expired, please log in again")

    meta = res.user.user_metadata or {}
    return {
        "id": res.user.id,
        "email": res.user.email,
        "full_name": meta.get("full_name", ""),
    }
