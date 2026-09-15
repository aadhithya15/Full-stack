"""Real recommendation plumbing, live-search payload, and quality retries."""
import json
from unittest.mock import Mock, patch

import pytest

from app.services.real_stylist import (
    _call_groq_research,
    _prompt,
    _strip_fences,
    _validate,
    get_real_recommendations,
)
from app.utils.errors import ApiError


def _look(index, outfit_type, main, main_hex, second, second_hex):
    titles = {1: "Peacock Ceremony", 2: "Ruby Heritage", 3: "Cobalt Celebration"}
    return {
        "outfit_name": titles.get(index, f"Distinct Look {index}"),
        "category": "traditional",
        "outfit_type": outfit_type,
        "materials": ["breathable handloom cotton"],
        "description": "A clear, coordinated Tamil occasion look with intentional contrast.",
        "garments": [
            {"item": "main garment", "name": f"{main} {outfit_type}", "colour": main, "fabric": "breathable handloom cotton"},
            {"item": "border", "name": f"{second} border", "colour": second, "fabric": "breathable handloom cotton"},
        ],
        "dress_colors": [
            {"name": main, "hex": main_hex},
            {"name": second, "hex": second_hex},
        ],
        "accessories": ["gold earrings", "woven clutch"],
        "footwear": "cushioned leather sandals",
        "styling_tips": "Keep the main colour nearest the face and all metal details gold.",
        "avoid_colors": [{"name": "Muddy Taupe", "hex": "#766B5F"}],
        "match_score": 90,
    }


GOOD_PAYLOAD = json.dumps({
    "detected_skin_tone": "wheatish complexion",
    "recommendations": [
        _look(1, "saree", "Peacock Teal", "#126A70", "Antique Gold", "#C59A43"),
        _look(2, "anarkali", "Ruby Maroon", "#7C2638", "Warm Ivory", "#EFE1C5"),
        _look(3, "lehenga-choli", "Cobalt Blue", "#2855A0", "Soft Peach", "#E49B78"),
    ],
})

ARGS = dict(
    skin_tone="wheatish",
    occasion="wedding",
    gender="female",
    style_preference="traditional",
    budget="medium",
    season_weather="hot",
    dress_type="let-ai-decide",
    preferred_material="let-ai-decide",
    language="en",
    notes="",
    count=3,
    exclude=[],
)


def test_strip_fences():
    assert json.loads(_strip_fences("```json\n{\"a\": 1}\n```")) == {"a": 1}


def test_validate_good_payload():
    detected, recos = _validate(GOOD_PAYLOAD, 3, skin_tone="wheatish", season_weather="hot")
    assert detected == "wheatish complexion"
    assert len(recos) == 3
    assert all(reco["is_mock"] is False for reco in recos)


def test_validate_rejects_bad_hex_instead_of_inventing_grey():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"][0]["dress_colors"][0]["hex"] = "greenish"
    with pytest.raises(ValueError, match="dress_colors"):
        _validate(json.dumps(bad), 3, skin_tone="wheatish")


def test_validate_rejects_rust_olive_for_deep_skin():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"][0] = _look(
        1, "saree", "Rust", "#A84F32", "Olive Green", "#66713C"
    )
    with pytest.raises(ValueError, match="rust and olive"):
        _validate(json.dumps(bad), 3, skin_tone="deep")


def test_validate_rejects_too_few():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"] = bad["recommendations"][:1]
    with pytest.raises(ValueError, match="expected 3"):
        _validate(json.dumps(bad), 3, skin_tone="wheatish")


def _fake_config(gemini="real-key", groq="real-key-2"):
    return patch.multiple(
        "app.services.real_stylist.Config",
        GEMINI_API_KEY=gemini,
        GROQ_API_KEY=groq,
    )


def test_gemini_success_after_one_internal_search():
    with _fake_config(), patch(
        "app.services.real_stylist._live_research", return_value="current Tamil fashion brief"
    ) as search, patch(
        "app.services.real_stylist._call_gemini", return_value=GOOD_PAYLOAD
    ) as gemini, patch("app.services.real_stylist._call_groq") as groq:
        _, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    search.assert_called_once()
    gemini.assert_called_once()
    groq.assert_not_called()


def test_fallback_to_groq_when_gemini_fails():
    with _fake_config(), patch(
        "app.services.real_stylist._live_research", return_value="live brief"
    ), patch(
        "app.services.real_stylist._call_gemini", side_effect=ValueError("boom")
    ) as gemini, patch(
        "app.services.real_stylist._call_groq", return_value=GOOD_PAYLOAD
    ) as groq:
        _, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    assert gemini.call_count == 3
    groq.assert_called_once()


def test_all_fail_raises_ai_unavailable_for_facade_to_catch():
    with _fake_config(), patch(
        "app.services.real_stylist._live_research", return_value=""
    ), patch(
        "app.services.real_stylist._call_gemini", side_effect=ValueError("boom")
    ), patch("app.services.real_stylist._call_groq", side_effect=ValueError("boom")):
        with pytest.raises(ApiError) as exc:
            get_real_recommendations(**ARGS)
    assert exc.value.code == "AI_UNAVAILABLE"


def test_retry_on_broken_json_adds_correction_then_succeeds():
    with _fake_config(groq="PLACEHOLDER_REPLACE_WHEN_AVAILABLE"), patch(
        "app.services.real_stylist._live_research", return_value="live brief"
    ), patch(
        "app.services.real_stylist._call_gemini",
        side_effect=["{not valid json", GOOD_PAYLOAD],
    ) as gemini:
        _, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    assert gemini.call_count == 2
    assert "CORRECTION REQUIRED" in gemini.call_args_list[1].args[0]


def test_compound_payload_enables_only_web_search_and_keeps_sources_internal():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Current Tamil guidance [1](https://example.com/article).",
                "executed_tools": [{
                    "type": "search",
                    "search_results": [{"url": "https://example.com/article"}],
                }],
            }
        }]
    }
    with patch("app.services.real_stylist.requests.post", return_value=response) as post:
        brief, domains = _call_groq_research("Use web search now")
    sent = post.call_args.kwargs["json"]
    assert sent["model"] == "groq/compound-mini"
    assert sent["compound_custom"]["tools"]["enabled_tools"] == ["web_search"]
    assert "https://" not in brief
    assert domains == ("example.com",)


def test_prompt_is_tamil_first_and_contains_quality_contract_not_image_generation():
    prompt = _prompt(
        skin_tone="deep",
        occasion="wedding",
        gender="female",
        style_preference="traditional",
        budget="medium",
        season_weather="hot",
        dress_type="saree",
        preferred_material="kanjivaram-silk",
        language="en",
        notes="",
        count=3,
        exclude=[],
        outfit_culture="tamil",
        outfit_formality="festive",
        age=42,
        research_brief="Current Kanjivaram border direction.",
    )
    assert "Tamil Nadu-first" in prompt
    assert "42 years old" in prompt
    assert "Rust plus olive is always rejected" in prompt
    assert "outfit_type must be one exact code" in prompt
    assert '"image_prompt"' not in prompt
    assert "<untrusted_web_research>" in prompt


def test_prompt_without_age_uses_adult_default():
    prompt = _prompt(
        skin_tone="dusky",
        occasion="party",
        gender="male",
        style_preference="casual",
        budget="low",
        season_weather="hot",
        dress_type="let-ai-decide",
        preferred_material="let-ai-decide",
        language="en",
        notes="",
        count=3,
        exclude=[],
    )
    assert "adult; exact age not specified" in prompt


@pytest.fixture()
def client_for_age():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with patch("app.middleware.auth_middleware.get_user_from_token") as get_user:
        get_user.return_value = {"id": "u-age", "email": "a@x.com", "full_name": "A"}
        with app.test_client() as client:
            yield client


def test_analyze_rejects_bad_age(client_for_age):
    response = client_for_age.post(
        "/api/fashion/analyze",
        data={"skin_tone_text": "wheatish", "occasion": "party", "gender": "female", "age": "abc"},
        headers={"Authorization": "Bearer x"},
    )
    assert response.status_code == 400
    response = client_for_age.post(
        "/api/fashion/analyze",
        data={"skin_tone_text": "wheatish", "occasion": "party", "gender": "female", "age": "60"},
        headers={"Authorization": "Bearer x"},
    )
    assert response.status_code == 400
