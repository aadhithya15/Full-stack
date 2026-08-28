"""Phase 1 tests: app boots, health works, error format is unified."""
import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["service"] == "huefit-api"
    assert data["status"] == "ok"
    # With placeholder keys, mock mode must be ON
    assert data["ai_mock_mode"] is True


def test_index_ok(client):
    res = client.get("/api/")
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_unknown_route_returns_unified_error(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]


def test_wrong_method_returns_unified_error(client):
    res = client.post("/api/health")
    assert res.status_code == 405
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_cors_headers_present_for_allowed_origin(client):
    res = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    res = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert res.headers.get("Access-Control-Allow-Origin") is None
