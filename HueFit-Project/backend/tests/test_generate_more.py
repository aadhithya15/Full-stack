"""Phase 7 tests - server-side anti-repetition for Generate More."""
import json
from unittest.mock import patch

import pytest

from app import create_app
from app.services.mock_stylist import generate_mock_recommendations

FAKE_USER = {"id": "u1", "email": "x@y.com", "full_name": "X"}
AUTH = {"Authorization": "Bearer x"}


@pytest.fixture()
def authed():
    app = create_app()
    app.config["TESTING"] = True
    with patch("app.middleware.auth_middleware.get_user_from_token") as mgu, patch(
        "app.routes.fashion_routes.queries.insert_analysis"
    ) as mia, patch(
        "app.routes.fashion_routes.queries.insert_recommendations"
    ) as mir, patch(
        "app.routes.fashion_routes.queries.list_past_outfit_names"
    ) as mlist:
        mgu.return_value = FAKE_USER
        mia.return_value = {"id": "an-1"}
        mir.side_effect = lambda uid, aid, recos: [
            {**r, "id": f"r{i}"} for i, r in enumerate(recos)
        ]
        mlist.return_value = []
        yield app.test_client(), mlist


def _analyze(client, **overrides):
    data = {
        "skin_tone_text": "wheatish",
        "occasion": "wedding",
        "gender": "female",
        "style_preference": "traditional",
    }
    data.update(overrides)
    return client.post("/api/fashion/analyze", data=data, headers=AUTH)


def test_server_side_history_excluded(authed):
    client, mlist = authed
    mlist.return_value = ["Emerald Green Silk Anarkali", "Rust Orange Lehenga Choli"]
    res = _analyze(client)
    assert res.status_code == 200
    names = {r["outfit_name"] for r in res.get_json()["recommendations"]}
    assert "Emerald Green Silk Anarkali" not in names
    assert "Rust Orange Lehenga Choli" not in names
    mlist.assert_called_once()


def test_avoid_repeats_false_skips_history(authed):
    client, mlist = authed
    res = _analyze(client, avoid_repeats="false")
    assert res.status_code == 200
    mlist.assert_not_called()


def test_history_failure_does_not_break_analysis(authed):
    client, mlist = authed
    mlist.side_effect = RuntimeError("db hiccup")
    res = _analyze(client)
    assert res.status_code == 200
    assert len(res.get_json()["recommendations"]) >= 3


def test_client_exclude_merged_with_history(authed):
    client, mlist = authed
    mlist.return_value = ["Olive Green Sharara Set"]
    res = _analyze(
        client, exclude=json.dumps(["Mustard Yellow Chikankari Kurta Set"])
    )
    names = {r["outfit_name"] for r in res.get_json()["recommendations"]}
    assert "Olive Green Sharara Set" not in names
    assert "Mustard Yellow Chikankari Kurta Set" not in names


def test_mock_stylist_survives_massive_exclusion():
    """Even with a huge exclusion list, we still get `count` outfits."""
    # First, collect a big set of names by running the generator repeatedly.
    excluded: set[str] = set()
    for _ in range(12):
        _, recos = generate_mock_recommendations(
            skin_tone="wheatish", occasion="wedding", gender="female",
            style_preference="traditional", budget="medium",
            season_weather="hot", count=5, exclude=sorted(excluded),
        )
        for r in recos:
            excluded.add(r["outfit_name"])

    # Now demand fresh outfits with everything so far excluded.
    _, final = generate_mock_recommendations(
        skin_tone="wheatish", occasion="wedding", gender="female",
        style_preference="traditional", budget="medium",
        season_weather="hot", count=5, exclude=sorted(excluded),
    )
    assert len(final) == 5
    final_names = {r["outfit_name"] for r in final}
    assert not final_names & excluded
