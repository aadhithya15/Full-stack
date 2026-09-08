"""Recommendation facade with an availability-preserving quality floor.

The route calls one function and keeps one response contract. Real provider
failures, malformed JSON, failed web search, or rejected colour palettes all
fall back to the same curated six-tone stylist rather than returning a 5xx.
"""
from __future__ import annotations

import logging

from app.config import Config
from app.services.mock_stylist import generate_mock_recommendations
from app.utils.errors import ApiError

log = logging.getLogger(__name__)


def _curated_fallback(**kwargs) -> tuple[str, list[dict]]:
    return generate_mock_recommendations(**kwargs)


def get_recommendations(
    skin_tone: str,
    occasion: str,
    gender: str,
    style_preference: str = "any",
    budget: str = "medium",
    season_weather: str = "any",
    dress_type: str = "let-ai-decide",
    preferred_material: str = "let-ai-decide",
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    age: int | None = None,
    language: str = "en",
    notes: str = "",
    count: int = 4,
    exclude: list[str] | None = None,
) -> tuple[str, list[dict]]:
    exclude = exclude or []
    fallback_args = {
        "skin_tone": skin_tone,
        "occasion": occasion,
        "gender": gender,
        "style_preference": style_preference,
        "budget": budget,
        "season_weather": season_weather,
        "dress_type": dress_type,
        "preferred_material": preferred_material,
        "outfit_culture": outfit_culture,
        "outfit_formality": outfit_formality,
        "age": age,
        "language": language,
        "notes": notes,
        "count": count,
        "exclude": exclude,
    }

    if Config.ai_mock_mode():
        return _curated_fallback(**fallback_args)

    from app.services.real_stylist import get_real_recommendations

    try:
        return get_real_recommendations(**fallback_args)
    except ApiError as exc:
        log.warning("real stylist unavailable (%s); using curated fallback", exc.code)
    except Exception as exc:
        log.exception("unexpected real stylist failure; using curated fallback: %s", exc)
    return _curated_fallback(**fallback_args)
