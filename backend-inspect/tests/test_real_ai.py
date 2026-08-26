"""Phase 5 tests - real AI plumbing with providers mocked (run offline)."""
import json
from unittest.mock import patch

import pytest

from app.services.real_stylist import _strip_fences, _validate, get_real_recommendations
from app.utils.errors import ApiError

GOOD_PAYLOAD = json.dumps(
    {
        "detected_skin_tone": "warm wheatish undertone",
        "recommendations": [
            {
                "outfit_name": f"Test Outfit {i}",
                "category": "traditional",
                "description": "A lovely outfit.",
                "dress_colors": [{"name": "Emerald", "hex": "#0F7B4D"}],
                "accessories": ["earrings", "clutch"],
                "footwear": "juttis",
                "styling_tips": "Keep it simple.",
                "avoid_colors": [{"name": "Grey", "hex": "#9E9E9E"}],
                "match_score": 90,
            }
            for i in range(3)
        ],
    }
)

ARGS = dict(
    skin_tone="wheatish", occasion="wedding", gender="female",
    style_preference="traditional", budget="medium", season_weather="hot",
    notes="", count=3, exclude=[],
)


def test_strip_fences():
    fenced = "```json\n{\"a\": 1}\n```"
    assert json.loads(_strip_fences(fenced)) == {"a": 1}


def test_validate_good_payload():
    detected, recos = _validate(GOOD_PAYLOAD, 3)
    assert detected == "warm wheatish undertone"
    assert len(recos) == 3
    assert recos[0]["is_mock"] is False


def test_validate_fixes_bad_hex():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"][0]["dress_colors"][0]["hex"] = "greenish"
    _, recos = _validate(json.dumps(bad), 3)
    assert recos[0]["dress_colors"][0]["hex"] == "#888888"


def test_validate_rejects_too_few():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"] = bad["recommendations"][:1]
    with pytest.raises(ValueError):
        _validate(json.dumps(bad), 3)


def _fake_config(gemini="real-key", groq="real-key-2"):
    return patch.multiple(
        "app.services.real_stylist.Config",
        GEMINI_API_KEY=gemini,
        GROQ_API_KEY=groq,
    )


def test_gemini_success():
    with _fake_config(), patch(
        "app.services.real_stylist._call_gemini", return_value=GOOD_PAYLOAD
    ) as mg, patch("app.services.real_stylist._call_groq") as mq:
        detected, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    mg.assert_called_once()
    mq.assert_not_called()


def test_fallback_to_groq_when_gemini_fails():
    with _fake_config(), patch(
        "app.services.real_stylist._call_gemini", side_effect=ValueError("boom")
    ) as mg, patch(
        "app.services.real_stylist._call_groq", return_value=GOOD_PAYLOAD
    ) as mq:
        detected, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    assert mg.call_count == 3  # three attempts before falling back
    mq.assert_called_once()


def test_all_fail_raises_ai_unavailable():
    with _fake_config(), patch(
        "app.services.real_stylist._call_gemini", side_effect=ValueError("boom")
    ), patch("app.services.real_stylist._call_groq", side_effect=ValueError("boom")):
        with pytest.raises(ApiError) as exc:
            get_real_recommendations(**ARGS)
    assert exc.value.code == "AI_UNAVAILABLE"


def test_retry_on_broken_json_then_success():
    with _fake_config(groq="PLACEHOLDER_REPLACE_WHEN_AVAILABLE"), patch(
        "app.services.real_stylist._call_gemini",
        side_effect=["{not valid json", GOOD_PAYLOAD],
    ) as mg:
        detected, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    assert mg.call_count == 2
