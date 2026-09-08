"""Phase 3 tests â€” auth endpoints.

Supabase calls are mocked, so these run offline and never touch your
real project. Live end-to-end auth is verified with check_auth.py.
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.utils.errors import ApiError


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


FAKE_USER = {"id": "user-123", "email": "priya@example.com", "full_name": "Priya S"}


# ------------------------------------------------------------- validation


def test_register_rejects_bad_email(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "longenough8", "full_name": "P"},
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_INPUT"


def test_register_rejects_short_password(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "a@b.com", "password": "short", "full_name": "P"},
    )
    assert res.status_code == 400
    assert "8 characters" in res.get_json()["error"]["message"]


def test_register_rejects_missing_body(client):
    res = client.post("/api/auth/register")
    assert res.status_code == 400


def test_login_rejects_bad_email(client):
    res = client.post("/api/auth/login", json={"email": "nope", "password": "x"})
    assert res.status_code == 400


# ---------------------------------------------------------------- success


def test_register_success(client):
    with patch("app.routes.auth_routes.auth_service.register") as mock_reg:
        mock_reg.return_value = {
            "token": "fake-jwt",
            "user": FAKE_USER,
            "needs_email_confirmation": False,
        }
        res = client.post(
            "/api/auth/register",
            json={
                "email": "priya@example.com",
                "password": "longenough8",
                "full_name": "Priya S",
            },
        )
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["token"] == "fake-jwt"
    assert data["user"]["email"] == "priya@example.com"


def test_login_success(client):
    with patch("app.routes.auth_routes.auth_service.login") as mock_login:
        mock_login.return_value = {"token": "fake-jwt", "user": FAKE_USER}
        res = client.post(
            "/api/auth/login",
            json={"email": "priya@example.com", "password": "longenough8"},
        )
    assert res.status_code == 200
    assert res.get_json()["token"] == "fake-jwt"


def test_login_wrong_password_gives_401(client):
    with patch("app.routes.auth_routes.auth_service.login") as mock_login:
        mock_login.side_effect = ApiError.unauthorized("Invalid email or password")
        res = client.post(
            "/api/auth/login",
            json={"email": "priya@example.com", "password": "wrongpass1"},
        )
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHORIZED"


# ------------------------------------------------------------- protection


def test_me_without_token_is_401(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_me_with_malformed_header_is_401(client):
    res = client.get("/api/auth/me", headers={"Authorization": "NotBearer xyz"})
    assert res.status_code == 401


def test_me_with_valid_token(client):
    with patch(
        "app.middleware.auth_middleware.get_user_from_token"
    ) as mock_get_user, patch("app.routes.auth_routes.queries.get_profile") as mock_prof:
        mock_get_user.return_value = FAKE_USER
        mock_prof.return_value = {"full_name": "Priya S", "skin_tone": "wheatish"}
        res = client.get("/api/auth/me", headers={"Authorization": "Bearer good-token"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["user"]["id"] == "user-123"
    assert data["profile"]["skin_tone"] == "wheatish"


def test_logout_requires_auth(client):
    res = client.post("/api/auth/logout")
    assert res.status_code == 401
