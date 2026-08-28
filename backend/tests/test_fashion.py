"""Phase 4 tests â€” /api/fashion/analyze in mock mode (DB mocked)."""
from unittest.mock import patch

import pytest

from app import create_app

FAKE_USER = {"id": "user-123", "email": "p@x.com", "full_name": "P"}


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def authed(client):
    """Client with auth mocked + DB writes mocked (echo back rows with ids)."""
    with patch("app.middleware.auth_middleware.get_user_from_token") as mgu, patch(
        "app.routes.fashion_routes.queries.insert_analysis"
    ) as mia, patch("app.routes.fashion_routes.queries.insert_recommendations") as mir:
        mgu.return_value = FAKE_USER
        mia.return_value = {"id": "analysis-1"}
        mir.side_effect = lambda uid, aid, recos: [
            {**r, "id": f"reco-{i}"} for i, r in enumerate(recos)
        ]
        yield client


AUTH = {"Authorization": "Bearer x"}


def _analyze(client, **overrides):
    data = {
        "skin_tone_text": "wheatish",
        "occasion": "wedding",
        "gender": "female",
        "style_preference": "traditional",
        "budget": "medium",
        "season_weather": "hot",
    }
    data.update(overrides)
    return client.post("/api/fashion/analyze", data=data, headers=AUTH)


def test_analyze_requires_auth(client):
    res = client.post("/api/fashion/analyze", data={"occasion": "party"})
    assert res.status_code == 401


def test_analyze_needs_skin_tone_or_photo(authed):
    res = _analyze(authed, skin_tone_text="")
    assert res.status_code == 400
    assert "photo" in res.get_json()["error"]["message"].lower()


def test_analyze_rejects_bad_occasion(authed):
    res = _analyze(authed, occasion="moonwalk")
    assert res.status_code == 400


def test_analyze_happy_path(authed):
    res = _analyze(authed)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["mock"] is True
    assert data["analysis_id"] == "analysis-1"
    recos = data["recommendations"]
    assert 3 <= len(recos) <= 5
    r = recos[0]
    for field in (
        "id", "outfit_name", "category", "description", "dress_colors",
        "accessories", "footwear", "styling_tips", "avoid_colors",
        "image_url", "match_score",
    ):
        assert field in r, f"missing field {field}"
    assert r["image_url"].startswith("https://image.pollinations.ai/")
    assert r["dress_colors"][0]["hex"].startswith("#")


def test_analyze_respects_count(authed):
    res = _analyze(authed, count="5")
    assert len(res.get_json()["recommendations"]) == 5


def test_generate_more_excludes_previous(authed):
    first = _analyze(authed).get_json()
    names = [r["outfit_name"] for r in first["recommendations"]]

    import json as _json

    second = _analyze(authed, exclude=_json.dumps(names)).get_json()
    second_names = {r["outfit_name"] for r in second["recommendations"]}
    assert not second_names & set(names), "excluded outfits reappeared"


def test_exclude_must_be_json_array(authed):
    res = _analyze(authed, exclude="not-json[")
    assert res.status_code == 400


def test_variety_between_calls(authed):
    a = {r["outfit_name"] for r in _analyze(authed).get_json()["recommendations"]}
    b = {r["outfit_name"] for r in _analyze(authed).get_json()["recommendations"]}
    # Random generation: at least SOME difference across two calls.
    assert a != b or len(a | b) > len(a)


def test_male_western_recos(authed):
    res = _analyze(authed, gender="male", style_preference="western")
    recos = res.get_json()["recommendations"]
    assert all(r["category"] == "western" for r in recos)
