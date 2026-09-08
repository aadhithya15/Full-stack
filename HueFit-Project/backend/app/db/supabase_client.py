"""Singleton Supabase client for the HueFit backend.

Uses the SERVICE ROLE key â€” full DB access, bypasses RLS â€” which is why
this key must NEVER reach the frontend or GitHub. All ownership checks
(user can only touch their own rows) are enforced in app/db/queries.py
by always filtering on user_id.
"""
from __future__ import annotations

from supabase import Client, create_client

from app.config import Config

_client: Client | None = None


class SupabaseNotConfigured(RuntimeError):
    """Raised when Supabase env vars are still placeholders."""


def get_supabase() -> Client:
    """Return the shared Supabase client (created lazily on first use)."""
    global _client
    if _client is None:
        if not Config.supabase_configured():
            raise SupabaseNotConfigured(
                "Supabase is not configured. Fill SUPABASE_URL and "
                "SUPABASE_SERVICE_KEY in your .env file (Supabase dashboard "
                "â†’ Settings â†’ API)."
            )
        _client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
    return _client


def reset_client() -> None:
    """Testing helper â€” forget the cached client."""
    global _client
    _client = None
