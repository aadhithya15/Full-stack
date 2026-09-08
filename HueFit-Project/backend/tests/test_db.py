"""Phase 2 tests â€” run WITHOUT a real Supabase account.

They verify the wiring: modules import, the client refuses to start with
placeholder credentials (clear error instead of a confusing crash), and
health still reports supabase_configured correctly.

Real end-to-end DB checks happen via `python check_supabase.py`
once your actual Supabase project exists.
"""
import pytest

from app import create_app
from app.config import Config
from app.db.supabase_client import SupabaseNotConfigured, get_supabase, reset_client


@pytest.fixture(autouse=True)
def _fresh_client():
    reset_client()
    yield
    reset_client()


def test_placeholder_credentials_raise_clear_error():
    if Config.supabase_configured():
        pytest.skip("Real Supabase credentials are configured")
    with pytest.raises(SupabaseNotConfigured):
        get_supabase()


def test_health_reports_supabase_state():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        data = c.get("/api/health").get_json()
    assert data["supabase_configured"] == Config.supabase_configured()


def test_queries_module_imports():
    """Catches syntax/import errors in the DB layer early."""
    from app.db import queries  # noqa: F401
    from app.services import storage_service  # noqa: F401

    assert callable(queries.get_profile)
    assert callable(queries.save_look)
    assert callable(storage_service.upload_photo)
