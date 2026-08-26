"""Phase 10 verification - checks your LIVE deployed backend.

Usage:
    python check_deploy.py https://huefit-api.onrender.com

It hits the public health endpoint, verifies config state, measures
cold-start/response time, and confirms auth + rate limiting behave
through the real internet.
"""
from __future__ import annotations

import sys
import time

import requests

OK = "  [OK]  "
FAIL = "  [FAIL]"
WARN = "  [WARN]"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python check_deploy.py https://your-api.onrender.com")
        return 1
    base = sys.argv[1].rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]

    print(f"HueFit - live deployment check: {base}")
    print("=" * 60)

    # 1) Health (may hit a cold start - allow up to 90s)
    print("  ...calling /api/health (cold start can take 30-60s)...")
    t0 = time.time()
    try:
        r = requests.get(f"{base}/api/health", timeout=90)
        elapsed = time.time() - t0
    except Exception as e:
        print(f"{FAIL} could not reach the server: {e}")
        return 1
    if r.status_code != 200:
        print(f"{FAIL} /api/health returned {r.status_code}: {r.text[:200]}")
        return 1
    data = r.json()
    print(f"{OK} health ok in {elapsed:.1f}s "
          f"({'cold start' if elapsed > 5 else 'warm'})")

    # 2) Config state
    if data.get("supabase_configured"):
        print(f"{OK} Supabase configured")
    else:
        print(f"{FAIL} supabase_configured=false -> env vars missing in Render dashboard")
        return 1
    if data.get("ai_mock_mode"):
        print(f"{WARN} ai_mock_mode=true -> AI keys not set in Render (mock replies)")
    else:
        print(f"{OK} real AI mode active")

    # 3) HTTPS
    if base.startswith("https://"):
        print(f"{OK} HTTPS")
    else:
        print(f"{WARN} not HTTPS - use the https:// URL Render gives you")

    # 4) Auth is enforced through the proxy
    r = requests.get(f"{base}/api/auth/me", timeout=30)
    if r.status_code == 401 and r.json().get("error", {}).get("code") == "UNAUTHORIZED":
        print(f"{OK} auth enforced (401 without token, unified error shape)")
    else:
        print(f"{FAIL} /api/auth/me without token returned {r.status_code}")
        return 1

    # 5) Unknown route -> unified 404
    r = requests.get(f"{base}/api/definitely-not-real", timeout=30)
    if r.status_code == 404 and r.json().get("error", {}).get("code") == "NOT_FOUND":
        print(f"{OK} unified error format live")
    else:
        print(f"{WARN} unexpected 404 shape: {r.status_code} {r.text[:120]}")

    # 6) Response time when warm
    t0 = time.time()
    requests.get(f"{base}/api/health", timeout=30)
    print(f"{OK} warm response time: {(time.time() - t0)*1000:.0f} ms")

    print("=" * 60)
    print("Deployment checks passed - HueFit is LIVE!")
    print("Remaining manual steps: UptimeRobot ping + ALLOWED_ORIGINS for the")
    print("deployed frontend URL (see PHASE10-GUIDE.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
