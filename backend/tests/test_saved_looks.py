"""Phase 8 tests - saved looks / wardrobe endpoints (DB mocked)."""
from unittest.mock import patch

import pytest

from app import create_app

FAKE_USER = {"id": "user-A", "email": "a@x.com", "full_name": "A"}
AUTH = {"Authorization": "Bearer x"}

RECO = {
    "id": "reco-1",
    "outfit_name": "Midnight Teal Anarkali",
    "category": "traditional",
    "dress_colors": [{"name": "Teal", "hex": "#006D77"}],
}

SAVED_ROW = {
    "id": "saved-1",
    "is_favourite": False,
    "saved_at": "2026-08-25T12:00:00Z",
    "recommendation": RECO,
}


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with patch("app.middleware.auth_middleware.get_user_from_token") as mgu:
        mgu.return_value = FAKE_USER
        with app.test_client() as c:
            yield c


# ------------------------------------------------------------------- save


def test_save_requires_auth():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        res = c.post("/api/fashion/save", json={"recommendation_id": "reco-1"})
    assert res.status_code == 401


def test_save_needs_recommendation_id(client):
    res = client.post("/api/fashion/save", json={}, headers=AUTH)
    assert res.status_code == 400


def test_save_happy_path(client):
    with patch(
        "app.routes.fashion_routes.queries.get_recommendation", return_value=RECO
    ) as mget, patch(
        "app.routes.fashion_routes.queries.save_look",
        return_value={"id": "saved-1"},
    ) as msave:
        res = client.post(
            "/api/fashion/save",
            json={"recommendation_id": "reco-1", "is_favourite": True},
            headers=AUTH,
        )
    assert res.status_code == 201
    assert res.get_json()["id"] == "saved-1"
    mget.assert_called_once_with("user-A", "reco-1")
    msave.assert_called_once_with("user-A", "reco-1", True)


def test_save_rejects_foreign_recommendation(client):
    """User B's recommendation id -> ownership check returns None -> 404."""
    with patch(
        "app.routes.fashion_routes.queries.get_recommendation", return_value=None
    ):
        res = client.post(
            "/api/fashion/save",
            json={"recommendation_id": "someone-elses-reco"},
            headers=AUTH,
        )
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------------------------- list


def test_list_saved(client):
    with patch(
        "app.routes.fashion_routes.queries.list_saved_looks",
        return_value=[SAVED_ROW],
    ) as mlist:
        res = client.get("/api/fashion/saved", headers=AUTH)
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["saved_looks"]) == 1
    look = data["saved_looks"][0]
    assert look["id"] == "saved-1"
    assert look["recommendation"]["outfit_name"] == "Midnight Teal Anarkali"
    mlist.assert_called_once_with("user-A")


def test_list_saved_empty(client):
    with patch(
        "app.routes.fashion_routes.queries.list_saved_looks", return_value=[]
    ):
        res = client.get("/api/fashion/saved", headers=AUTH)
    assert res.status_code == 200
    assert res.get_json()["saved_looks"] == []


# -------------------------------------------------------------- favourite


def test_toggle_favourite(client):
    with patch(
        "app.routes.fashion_routes.queries.set_favourite", return_value=True
    ) as mset:
        res = client.patch(
            "/api/fashion/saved/saved-1",
            json={"is_favourite": True},
            headers=AUTH,
        )
    assert res.status_code == 200
    mset.assert_called_once_with("user-A", "saved-1", True)


def test_favourite_needs_body(client):
    res = client.patch("/api/fashion/saved/saved-1", json={}, headers=AUTH)
    assert res.status_code == 400


def test_favourite_foreign_look_is_404(client):
    """Ownership: set_favourite filters by user_id -> no rows -> 404."""
    with patch(
        "app.routes.fashion_routes.queries.set_favourite", return_value=False
    ):
        res = client.patch(
            "/api/fashion/saved/not-mine",
            json={"is_favourite": True},
            headers=AUTH,
        )
    assert res.status_code == 404


# ----------------------------------------------------------------- delete


def test_delete_saved(client):
    with patch(
        "app.routes.fashion_routes.queries.delete_saved_look", return_value=True
    ) as mdel:
        res = client.delete("/api/fashion/saved/saved-1", headers=AUTH)
    assert res.status_code == 200
    mdel.assert_called_once_with("user-A", "saved-1")


def test_delete_foreign_look_is_404(client):
    with patch(
        "app.routes.fashion_routes.queries.delete_saved_look", return_value=False
    ):
        res = client.delete("/api/fashion/saved/not-mine", headers=AUTH)
    assert res.status_code == 404
