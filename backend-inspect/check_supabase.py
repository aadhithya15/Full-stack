"""Phase 2 verification script.

Run AFTER you have:
  1. Created the Supabase project,
  2. Pasted your real SUPABASE_URL / SUPABASE_SERVICE_KEY / SUPABASE_JWT_SECRET into .env,
  3. Run migrations/001_init.sql in the Supabase SQL Editor.

Usage:
    python check_supabase.py

It checks the connection, all four tables, and creates the private
'user-uploads' storage bucket if missing. All checks green = Phase 2 done.
"""
from __future__ import annotations

import sys

OK = "  [OK]  "
FAIL = "  [FAIL]"

def main() -> int:
    from app.config import Config

    print("HueFit â€” Supabase connection check")
    print("=" * 50)

    # 1) Env vars filled in?
    if not Config.supabase_configured():
        print(f"{FAIL} .env still has placeholder SUPABASE_URL / SUPABASE_SERVICE_KEY.")
        print("        Fill them from: Supabase dashboard -> Settings -> API")
        return 1
    print(f"{OK} .env has Supabase credentials")

    if Config.is_placeholder(Config.SUPABASE_JWT_SECRET):
        print(f"{FAIL} SUPABASE_JWT_SECRET is still a placeholder (needed in Phase 3).")
        print("        Find it: Settings -> API -> JWT Settings -> JWT Secret")
        return 1
    print(f"{OK} SUPABASE_JWT_SECRET is set")

    # 2) Can we connect?
    try:
        from app.db.supabase_client import get_supabase
        sb = get_supabase()
    except Exception as e:
        print(f"{FAIL} Could not create client: {e}")
        return 1
    print(f"{OK} Client created")

    # 3) Do the four tables exist?
    tables = ["profiles", "analyses", "recommendations", "saved_looks"]
    all_ok = True
    for t in tables:
        try:
            sb.table(t).select("*", count="exact").limit(0).execute()
            print(f"{OK} table '{t}' exists")
        except Exception as e:
            all_ok = False
            print(f"{FAIL} table '{t}' missing or unreadable -> run migrations/001_init.sql")
            print(f"        ({type(e).__name__}: {str(e)[:100]})")
    if not all_ok:
        return 1

    # 4) Storage bucket
    from app.services.storage_service import BUCKET, ensure_bucket
    if ensure_bucket():
        print(f"{OK} storage bucket '{BUCKET}' ready (private)")
    else:
        print(f"{FAIL} could not verify/create bucket '{BUCKET}' â€” create it manually:")
        print("        Dashboard -> Storage -> New bucket -> name: user-uploads -> Public: OFF")
        return 1

    print("=" * 50)
    print("All checks passed â€” Phase 2 complete! Next: Phase 3 (auth).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
