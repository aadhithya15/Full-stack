"""Phase 3 LIVE verification â€” tests real auth against your Supabase project.

Run with the Flask server NOT needed (talks to Supabase directly through
the service layer), venv active:

    python check_auth.py

It will:
  1. register a throwaway test user,
  2. log in with it,
  3. validate the token (like @require_auth does),
  4. read the auto-created profile row,
  5. clean up (delete the test user).

All green = Phase 3 complete.
"""
from __future__ import annotations

import sys
import time

OK = "  [OK]  "
FAIL = "  [FAIL]"


def main() -> int:
    from app import create_app

    app = create_app()
    with app.app_context():
        from app.db import queries
        from app.db.supabase_client import get_supabase
        from app.services import auth_service

        email = f"huefit.test.{int(time.time())}@example.com"
        password = "TestPass123!"

        print("HueFit â€” live auth check")
        print("=" * 50)
        print(f"  test user: {email}")

        # 1) Register
        try:
            reg = auth_service.register(email, password, "Test User")
        except Exception as e:
            print(f"{FAIL} register failed: {e}")
            return 1
        print(f"{OK} register worked (user id: {reg['user']['id'][:8]}...)")

        if reg["needs_email_confirmation"]:
            print(f"{FAIL} Email confirmation is ON in Supabase â€” for the MVP, turn it OFF:")
            print("        Dashboard -> Authentication -> Sign In / Providers ->")
            print("        Email -> disable 'Confirm email' -> Save")
            print("        Then run this script again.")
            _cleanup(get_supabase(), reg["user"]["id"])
            return 1
        print(f"{OK} session issued immediately (email confirmation off)")

        # 2) Login
        try:
            log = auth_service.login(email, password)
        except Exception as e:
            print(f"{FAIL} login failed: {e}")
            _cleanup(get_supabase(), reg["user"]["id"])
            return 1
        print(f"{OK} login worked, token received")

        # 3) Token validation (what @require_auth does)
        try:
            user = auth_service.get_user_from_token(log["token"])
            assert user["id"] == reg["user"]["id"]
        except Exception as e:
            print(f"{FAIL} token validation failed: {e}")
            _cleanup(get_supabase(), reg["user"]["id"])
            return 1
        print(f"{OK} token validates -> user identified")

        # 4) Auto-created profile (the DB trigger from Phase 2)
        profile = queries.get_profile(user["id"])
        if profile is None:
            print(f"{FAIL} profile row missing â€” did migration 001 run fully?")
            _cleanup(get_supabase(), reg["user"]["id"])
            return 1
        print(f"{OK} profile auto-created by trigger (full_name: '{profile.get('full_name')}')")

        # 5) Cleanup
        if _cleanup(get_supabase(), reg["user"]["id"]):
            print(f"{OK} test user deleted")
        else:
            print("  [WARN] could not delete test user (harmless â€” remove in dashboard)")

        print("=" * 50)
        print("All checks passed â€” Phase 3 complete! Next: Phase 4 (/analyze).")
        return 0


def _cleanup(_unused, user_id: str) -> bool:
    """Delete the test user with a FRESH service-key client.

    The shared client may hold the test user's session after sign_up/sign_in
    and would send that user's token to the admin API -> 403 not_admin.
    A fresh client sends only the service key, which has admin rights.
    """
    try:
        from supabase import create_client

        from app.config import Config

        admin = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
        admin.auth.admin.delete_user(user_id)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
