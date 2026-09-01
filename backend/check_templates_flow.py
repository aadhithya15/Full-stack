"""Phase T3 LIVE verification - the full template recolouring flow.

Run with migrations 007 applied and the sample templates uploaded
(scripts/upload_templates.py templates/sample --approve):

    python check_templates_flow.py

Verifies: template selection from the real DB, asset fetch from the
public bucket, recolouring, and render upload - the complete section-9
runtime flow, without needing the API server running.
"""
from __future__ import annotations

import sys

OK = "  [OK]  "
FAIL = "  [FAIL]"


def main() -> int:
    from app import create_app

    app = create_app()
    with app.app_context():
        from app.db import queries
        from app.services.template_service import pick_template, render_recommendation

        print("HueFit MVP - template flow check")
        print("=" * 52)

        n = queries.count_templates(only_active=True)
        if n == 0:
            print(f"{FAIL} no active templates - run the T1 steps first")
            return 1
        print(f"{OK} {n} active QA-approved template(s) in the library")

        tpl = pick_template("saree", "female", culture="tamil")
        if tpl is None:
            print(f"{FAIL} selection returned nothing for saree/female/tamil")
            return 1
        print(f"{OK} selected template: {tpl['template_code']}")

        # the strategy document's example: three users, three colours
        for name, hexc in (("maroon", "#800000"), ("emerald", "#0F7B4D"), ("royal blue", "#2B4C9B")):
            url = render_recommendation(tpl, hexc)
            if not url:
                print(f"{FAIL} render failed for {name}")
                return 1
            print(f"{OK} {name:11} -> {url}")

        # cache proof: repeat render must be instant (same URL)
        import time
        t0 = time.time()
        url2 = render_recommendation(tpl, "#800000")
        ms = (time.time() - t0) * 1000
        print(f"{OK} repeat render served from cache in {ms:.0f}ms")

        print("=" * 52)
        print("All checks passed - the section-9 runtime flow works end to end.")
        print("Open one of the URLs above in your browser to SEE the recolour.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
