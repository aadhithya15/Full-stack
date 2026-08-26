"""Phase 6 tests - skin tone detection (vision mocked, Pillow real)."""
import io
from unittest.mock import patch

import pytest

from app.services.skin_tone_service import (
    _detect_with_pillow,
    detect_skin_tone,
)


def _make_photo(rgb: tuple[int, int, int]) -> bytes:
    """Create a small in-memory JPEG of a flat 'skin' colour."""
    from PIL import Image

    img = Image.new("RGB", (200, 260), rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ------------------------------------------------------------ pillow layer


def test_pillow_detects_fair_skin():
    label = _detect_with_pillow(_make_photo((236, 215, 202)))
    assert label is not None
    assert any(w in label for w in ("fair", "light"))


def test_pillow_detects_wheatish_skin():
    label = _detect_with_pillow(_make_photo((190, 145, 110)))
    assert label is not None
    assert "medium" in label or "wheatish" in label


def test_pillow_detects_deep_skin():
    label = _detect_with_pillow(_make_photo((95, 65, 50)))
    assert label is not None
    assert any(w in label for w in ("deep", "dusky"))


def test_pillow_warm_undertone():
    label = _detect_with_pillow(_make_photo((200, 150, 105)))
    assert "warm" in label


def test_pillow_handles_garbage_bytes():
    assert _detect_with_pillow(b"not an image at all") is None


# ------------------------------------------------------------ orchestration


def test_vision_preferred_over_pillow():
    with patch(
        "app.services.skin_tone_service._detect_with_gemini",
        return_value="warm wheatish (golden glow)",
    ) as mv:
        label = detect_skin_tone(_make_photo((190, 145, 110)), "image/jpeg")
    assert label == "warm wheatish (golden glow)"
    mv.assert_called_once()


def test_falls_back_to_pillow_when_vision_fails():
    with patch(
        "app.services.skin_tone_service._detect_with_gemini", return_value=None
    ):
        label = detect_skin_tone(_make_photo((190, 145, 110)), "image/jpeg")
    assert label != "medium neutral"  # pillow produced something real
    assert any(w in label for w in ("warm", "cool", "neutral"))


def test_safe_default_when_everything_fails():
    with patch(
        "app.services.skin_tone_service._detect_with_gemini", return_value=None
    ), patch(
        "app.services.skin_tone_service._detect_with_pillow", return_value=None
    ):
        assert detect_skin_tone(b"x", "image/jpeg") == "medium neutral"


# -------------------------------------------------------- analyze with photo


def test_analyze_with_photo_uses_detection(client_with_auth):
    client = client_with_auth
    with patch(
        "app.services.skin_tone_service.detect_skin_tone"
    ) as md, patch(
        "app.routes.fashion_routes.__name__", "app.routes.fashion_routes"
    ):
        md.return_value = "warm dusky (rich golden tone)"
        with patch("app.services.storage_service.upload_photo", return_value="u1/p.jpg"):
            res = client.post(
                "/api/fashion/analyze",
                data={
                    "occasion": "party",
                    "gender": "female",
                    "photo": (io.BytesIO(_make_photo((150, 105, 80))), "me.jpg", "image/jpeg"),
                },
                headers={"Authorization": "Bearer x"},
            )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    # detection result flows into the response
    assert "dusky" in data["detected_skin_tone"] or "warm" in data["detected_skin_tone"]


@pytest.fixture()
def client_with_auth():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with patch("app.middleware.auth_middleware.get_user_from_token") as mgu, patch(
        "app.routes.fashion_routes.queries.insert_analysis"
    ) as mia, patch("app.routes.fashion_routes.queries.insert_recommendations") as mir:
        mgu.return_value = {"id": "u1", "email": "x@y.com", "full_name": "X"}
        mia.return_value = {"id": "an-1"}
        mir.side_effect = lambda uid, aid, recos: [
            {**r, "id": f"r{i}"} for i, r in enumerate(recos)
        ]
        with app.test_client() as c:
            yield c
