"""Six-tone colour-story quality floor and curated fallback tests."""
from unittest.mock import patch

import pytest

from app.services import ai_service
from app.services.mock_stylist import generate_mock_recommendations
from app.services.outfit_quality import (
    PALETTE_STORIES,
    batch_issues,
    canonical_depth,
    recommendation_issues,
)
from app.utils.errors import ApiError

TONES = ("fair", "light", "wheatish", "medium", "dusky", "deep")


def _generate(tone, **overrides):
    args = {
        "skin_tone": tone,
        "occasion": "wedding",
        "gender": "female",
        "style_preference": "traditional",
        "budget": "medium",
        "season_weather": "hot",
        "dress_type": "let-ai-decide",
        "preferred_material": "let-ai-decide",
        "outfit_culture": "tamil",
        "outfit_formality": "festive",
        "age": 28,
        "language": "en",
        "notes": "",
        "count": 5,
        "exclude": [],
    }
    args.update(overrides)
    return generate_mock_recommendations(**args)


def test_user_selected_depth_wins_over_photo_description():
    assert canonical_depth("warm medium from photo (user selected: deep)") == "deep"
    assert canonical_depth("cool light from photo (user selected: dusky)") == "dusky"


@pytest.mark.parametrize("tone", TONES)
def test_each_public_tone_has_eight_complete_curated_stories(tone):
    stories = PALETTE_STORIES[tone]
    assert len(stories) >= 8
    signatures = set()
    for story in stories:
        assert story["main"][1].startswith("#")
        assert story["secondary"][1].startswith("#")
        signature = (story["main"][1], story["secondary"][1])
        assert signature not in signatures
        signatures.add(signature)


@pytest.mark.parametrize("tone", TONES)
def test_full_backend_fallback_exercises_every_tone_without_quality_issues(tone):
    detected, recommendations = _generate(tone)
    assert tone in detected
    assert len(recommendations) == 5
    problems = batch_issues(
        recommendations,
        count=5,
        exclude=[],
        skin_tone=tone,
        dress_type="let-ai-decide",
        preferred_material="let-ai-decide",
        outfit_culture="tamil",
        outfit_formality="festive",
        season_weather="hot",
        age=28,
        notes="",
    )
    assert problems == []


@pytest.mark.parametrize("tone", ("dusky", "deep"))
def test_deeper_tones_never_receive_two_earth_colours_in_curated_fallback(tone):
    earth = {"rust", "rusty", "olive", "khaki", "camel", "taupe", "brown", "terracotta", "ochre"}
    for _ in range(30):
        _, recommendations = _generate(tone)
        for recommendation in recommendations:
            names = " ".join(colour["name"].lower() for colour in recommendation["dress_colors"])
            used = {word for word in earth if word in names}
            assert len(used) < 2
            assert not ({"rust", "olive"} <= used)


def test_quality_gate_rejects_muddy_rust_olive_even_with_valid_shape():
    _, recommendations = _generate("deep", count=3)
    recommendation = recommendations[0]
    recommendation["dress_colors"] = [
        {"name": "Rust", "hex": "#A84F32"},
        {"name": "Olive Green", "hex": "#66713C"},
    ]
    recommendation["garments"][0]["name"] = "Rust main garment"
    recommendation["garments"][0]["colour"] = "Rust"
    recommendation["garments"][1]["name"] = "Olive Green border"
    recommendation["garments"][1]["colour"] = "Olive Green"
    problems = recommendation_issues(
        recommendation,
        skin_tone="deep",
        season_weather="hot",
    )
    assert any("rust and olive" in problem for problem in problems)
    assert any("two muted earth" in problem for problem in problems)


def test_quality_gate_rejects_fluorescent_and_name_hex_conflict():
    _, recommendations = _generate("medium", count=3)
    recommendation = recommendations[0]
    recommendation["dress_colors"][0] = {"name": "Fluorescent Emerald Green", "hex": "#FF0000"}
    recommendation["garments"][0]["name"] = "Fluorescent Emerald Green main garment"
    recommendation["garments"][0]["colour"] = "Fluorescent Emerald Green"
    problems = recommendation_issues(recommendation, skin_tone="medium")
    assert any("fluorescent" in problem for problem in problems)
    assert any("does not match its hex" in problem for problem in problems)


def test_explicit_type_material_culture_age_and_colour_note_are_preserved():
    _, recommendations = _generate(
        "deep",
        occasion="party",
        style_preference="western",
        dress_type="midi-dress",
        preferred_material="linen",
        outfit_culture="western",
        outfit_formality="party",
        age=16,
        notes="no red",
    )
    assert all(item["outfit_type"] == "midi-dress" for item in recommendations)
    assert all("linen" in " ".join(item["materials"]).lower() for item in recommendations)
    assert all(item["category"] == "western" for item in recommendations)
    assert all("red" not in " ".join(colour["name"].lower() for colour in item["dress_colors"]) for item in recommendations)
    assert all("teen" in item["description"].lower() for item in recommendations)


@pytest.mark.parametrize("tone", TONES)
def test_analyze_endpoint_returns_a_quality_story_for_each_public_tone(tone):
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with patch("app.middleware.auth_middleware.get_user_from_token") as get_user, patch(
        "app.routes.fashion_routes.queries.get_profile", return_value={"language": "en"}
    ), patch(
        "app.routes.fashion_routes.queries.list_past_outfit_names", return_value=[]
    ), patch(
        "app.routes.fashion_routes.queries.insert_analysis", return_value={"id": "analysis-tone"}
    ), patch(
        "app.routes.fashion_routes.queries.insert_recommendations"
    ) as insert_recommendations, patch(
        "app.services.template_service.pick_template", return_value=None
    ):
        get_user.return_value = {"id": "tone-user", "email": "tone@example.com"}
        insert_recommendations.side_effect = lambda user_id, analysis_id, recos: [
            {**reco, "id": f"reco-{index}"} for index, reco in enumerate(recos)
        ]
        response = app.test_client().post(
            "/api/fashion/analyze",
            data={
                "skin_tone": tone,
                "occasion": "wedding",
                "gender": "female",
                "style_preference": "traditional",
                "outfit_culture": "tamil",
                "outfit_formality": "festive",
                "season_weather": "hot",
                "count": "3",
            },
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 200
    body = response.get_json()
    assert body["canonical_tone"] == tone
    assert body["mock"] is True
    assert len(body["recommendations"]) == 3
    for recommendation in body["recommendations"]:
        names = " ".join(colour["name"].lower() for colour in recommendation["dress_colors"])
        assert not ("rust" in names and "olive" in names)


def test_real_provider_api_error_degrades_to_curated_output_not_availability():
    with patch.object(ai_service.Config, "ai_mock_mode", return_value=False), patch(
        "app.services.real_stylist.get_real_recommendations",
        side_effect=ApiError.ai_unavailable("provider down"),
    ):
        detected, recommendations = ai_service.get_recommendations(
            skin_tone="deep",
            occasion="wedding",
            gender="female",
            style_preference="traditional",
            budget="medium",
            season_weather="hot",
            dress_type="saree",
            preferred_material="kanjivaram-silk",
            outfit_culture="tamil",
            outfit_formality="festive",
            age=32,
            language="en",
            notes="",
            count=3,
            exclude=[],
        )
    assert "deep" in detected
    assert len(recommendations) == 3
    assert all(item["is_mock"] is True for item in recommendations)
    assert all(item["outfit_type"] == "saree" for item in recommendations)
    assert all("kanjivaram silk" in item["materials"][0] for item in recommendations)
