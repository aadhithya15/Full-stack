"""Phase 5 LIVE verification - tests the real AI providers.

Run after putting at least one real key (GEMINI_API_KEY / GROQ_API_KEY)
into .env:

    python check_ai.py

It calls the real provider(s) with a sample request and prints the first
recommendation, so you can see genuine AI output before wiring the demo.
"""
from __future__ import annotations

import json
import sys

OK = "  [OK]  "
FAIL = "  [FAIL]"


def main() -> int:
    from app import create_app

    app = create_app()
    with app.app_context():
        from app.config import Config

        print("HueFit - live AI check")
        print("=" * 50)

        gem = not Config.is_placeholder(Config.GEMINI_API_KEY)
        grq = not Config.is_placeholder(Config.GROQ_API_KEY)
        print(f"{OK if gem else FAIL} GEMINI_API_KEY {'set' if gem else 'is still a placeholder'}")
        print(f"{OK if grq else FAIL} GROQ_API_KEY {'set' if grq else 'is still a placeholder'}")

        if Config.ai_mock_mode():
            print(f"{FAIL} Both keys are placeholders -> still in mock mode.")
            print("        Put at least one real key in .env, then rerun.")
            return 1

        from app.services.ai_service import get_recommendations

        print("  ...calling the AI (can take 5-20 seconds)...")
        try:
            detected, recos = get_recommendations(
                skin_tone="wheatish",
                occasion="wedding",
                gender="female",
                style_preference="traditional",
                budget="medium",
                season_weather="hot",
                notes="",
                count=3,
                exclude=[],
            )
        except Exception as e:
            print(f"{FAIL} AI call failed: {e}")
            print("        Check the key is correct and has quota left.")
            return 1

        mock = bool(recos and recos[0].get("is_mock"))
        if mock:
            print(f"{FAIL} Got MOCK results - real provider failed, fallback kicked in.")
            print("        Check server logs / key validity and rerun.")
            return 1

        print(f"{OK} REAL AI responded with {len(recos)} recommendations")
        print(f"{OK} detected skin tone: {detected}")
        print()
        print("First recommendation from the real AI:")
        print("-" * 50)
        r = recos[0]
        print(json.dumps(
            {k: r[k] for k in (
                "outfit_name", "category", "description", "dress_colors",
                "accessories", "footwear", "styling_tips", "avoid_colors", "match_score",
            )},
            indent=2, ensure_ascii=False,
        ))
        print("-" * 50)
        print("=" * 50)
        print("All checks passed - Phase 5 complete! The app now uses real AI.")
        print('(/api/fashion/analyze responses will show "mock": false)')
        return 0


if __name__ == "__main__":
    sys.exit(main())
