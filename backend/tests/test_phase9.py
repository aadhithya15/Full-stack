"""Phase 9 tests - rate limiting + profile endpoints."""
from unittest.mock import patch

import pytest

from app import create_app
from app.middleware.rate_limit import reset_limits

FAKE_USER = {"id": "user-9", "email": "p9@x.com", "full_name": "P9"}
AUTH = {"Authorization": "Bearer x"}


@pytest.fixture(autouse=True)
def _clean_limits():
    reset_limits()
    yield
    reset_limits()


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with patch("app.middleware.auth_middleware.get_user_from_token") as mgu:
        mgu.return_value = FAKE_USER
        with app.test_client() as c:
            yield c


# ------------------------------------------------------------ rate limits


def test_login_rate_limit(client):
    """6th login attempt within a minute -> 429."""
    with patch("app.routes.auth_routes.auth_service.login") as mlogin:
        from app.utils.errors import ApiError

        mlogin.side_effect = ApiError.unauthorized("Invalid email or password")
        for i in range(5):
            res = client.post(
                "/api/auth/login",
                json={"email": "a@b.com", "password": "wrongpass1"},
            )
            assert res.status_code == 401, f"attempt {i+1}"
        res = client.post(
            "/api/auth/login", json={"email": "a@b.com", "password": "wrongpass1"}
        )
    assert res.status_code == 429
    data = res.get_json()
    assert data["error"]["code"] == "RATE_LIMITED"
    assert "try again" in data["error"]["message"]


def test_analyze_rate_limit(client):
    """9th analyze in a minute -> 429 (limit 8/min per user)."""
    with patch("app.routes.fashion_routes.queries.insert_analysis") as mia, patch(
        "app.routes.fashion_routes.queries.insert_recommendations"
    ) as mir, patch(
        "app.routes.fashion_routes.queries.list_past_outfit_names", return_value=[]
    ):
        mia.return_value = {"id": "an-1"}
        mir.side_effect = lambda uid, aid, recos: [
            {**r, "id": f"r{i}"} for i, r in enumerate(recos)
        ]
        for i in range(8):
            res = client.post(
                "/api/fashion/analyze",
                data={"skin_tone_text": "wheatish", "occasion": "party", "gender": "female"},
                headers=AUTH,
            )
            assert res.status_code == 200, f"call {i+1}"
        res = client.post(
            "/api/fashion/analyze",
            data={"skin_tone_text": "wheatish", "occasion": "party", "gender": "female"},
            headers=AUTH,
        )
    assert res.status_code == 429


def test_rate_limit_is_per_user(client):
    """A different user is NOT blocked by user-9's exhausted quota."""
    with patch("app.routes.fashion_routes.queries.insert_analysis") as mia, patch(
        "app.routes.fashion_routes.queries.insert_recommendations"
    ) as mir, patch(
        "app.routes.fashion_routes.queries.list_past_outfit_names", return_value=[]
    ), patch(
        "app.middleware.auth_middleware.get_user_from_token"
    ) as mgu:
        mia.return_value = {"id": "an-1"}
        mir.side_effect = lambda uid, aid, recos: [
            {**r, "id": f"r{i}"} for i, r in enumerate(recos)
        ]
        mgu.return_value = FAKE_USER
        for _ in range(8):
            client.post(
                "/api/fashion/analyze",
                data={"skin_tone_text": "wheatish", "occasion": "party", "gender": "female"},
                headers=AUTH,
            )
        # switch identity
        mgu.return_value = {"id": "user-OTHER", "email": "o@x.com", "full_name": "O"}
        res = client.post(
            "/api/fashion/analyze",
            data={"skin_tone_text": "wheatish", "occasion": "party", "gender": "female"},
            headers=AUTH,
        )
    assert res.status_code == 200


# ---------------------------------------------------------------- profile


def test_get_profile(client):
    with patch(
        "app.routes.profile_routes.queries.get_profile",
        return_value={"full_name": "P9", "skin_tone": "wheatish"},
    ):
        res = client.get("/api/profile", headers=AUTH)
    assert res.status_code == 200
    data = res.get_json()
    assert data["profile"]["skin_tone"] == "wheatish"
    assert data["user"]["id"] == "user-9"


def test_get_profile_requires_auth():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        assert c.get("/api/profile").status_code == 401


def test_update_profile(client):
    with patch("app.routes.profile_routes.queries.upsert_profile") as mup:
        mup.return_value = {"full_name": "New Name", "default_budget": "premium"}
        res = client.put(
            "/api/profile",
            json={"full_name": "New Name", "default_budget": "premium"},
            headers=AUTH,
        )
    assert res.status_code == 200
    mup.assert_called_once_with(
        "user-9", {"full_name": "New Name", "default_budget": "premium"}
    )


def test_update_profile_rejects_bad_enum(client):
    res = client.put("/api/profile", json={"gender": "alien"}, headers=AUTH)
    assert res.status_code == 400


def test_update_profile_rejects_unknown_only(client):
    res = client.put("/api/profile", json={"hacker_field": "x"}, headers=AUTH)
    assert res.status_code == 400


def test_update_profile_rejects_empty_body(client):
    res = client.put("/api/profile", json={}, headers=AUTH)
    assert res.status_code == 400
