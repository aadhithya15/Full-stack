"""AI recommendation facade.

ONE public function: get_recommendations(...).
  - Mock mode (AI keys are placeholders): uses mock_stylist. Everything
    works end-to-end ? auth, DB, images ? with realistic varied content.
  - Real mode (Phase 5): calls Gemini (primary) / Groq (fallback) and
    parses strict JSON. Same return shape; routes never change.

Return: (detected_skin_tone: str, recommendations: list[dict])
Each recommendation dict has: outfit_name, category, description,
dress_colors, accessories, footwear, styling_tips, avoid_colors,
match_score, is_mock  ? image_url is added by the route (image_service).
"""
from __future__ import annotations

from app.config import Config
from app.services.mock_stylist import generate_mock_recommendations
from app.utils.errors import ApiError


def get_recommendations(
    skin_tone: str,
    occasion: str,
    gender: str,
    style_preference: str = "any",
    budget: str = "medium",
    season_weather: str = "any",
    dress_type: str = "let-ai-decide",
    preferred_material: str = "let-ai-decide",
    language: str = "en",
    notes: str = "",
    count: int = 4,
    exclude: list[str] | None = None,
) -> tuple[str, list[dict]]:
    exclude = exclude or []

    if Config.ai_mock_mode():
        return generate_mock_recommendations(
            skin_tone=skin_tone,
            occasion=occasion,
            gender=gender,
            style_preference=style_preference,
            budget=budget,
            season_weather=season_weather,
            dress_type=dress_type,
            preferred_material=preferred_material,
            language=language,
            count=count,
            exclude=exclude,
        )

    # Real mode: Gemini (primary) -> Groq (fallback), strict JSON.
    from app.services.real_stylist import get_real_recommendations

    try:
        return get_real_recommendations(
            skin_tone=skin_tone,
            occasion=occasion,
            gender=gender,
            style_preference=style_preference,
            budget=budget,
            season_weather=season_weather,
            dress_type=dress_type,
            preferred_material=preferred_material,
            language=language,
            notes=notes,
            count=count,
            exclude=exclude,
        )
    except ApiError:
        raise
    except Exception:
        # Absolute last resort: never give the user a hard failure when the
        # mock stylist can still produce a usable answer.
        return generate_mock_recommendations(
            skin_tone=skin_tone,
            occasion=occasion,
            gender=gender,
            style_preference=style_preference,
            budget=budget,
            season_weather=season_weather,
            dress_type=dress_type,
            preferred_material=preferred_material,
            language=language,
            count=count,
            exclude=exclude,
        )
