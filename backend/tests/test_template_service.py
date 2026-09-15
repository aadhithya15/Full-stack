"""Phase T3 tests - template selection + render flow (network/DB mocked)."""
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services import template_service
from app.services.template_service import pick_template, render_recommendation

TPL_ROW = {
    "template_code": "saree_f_01",
    "image_url": "https://x/templates/saree_f_01/saree_f_01.jpg",
    "mask_url": "https://x/templates/saree_f_01/saree_f_01_mask.png",
}


@pytest.fixture(autouse=True)
def _fresh():
    template_service.clear_caches()
    yield
    template_service.clear_caches()


# ------------------------------------------------------------ pick_template


def test_pick_exact_match_first():
    with patch("app.services.template_service.queries.select_templates") as m:
        m.return_value = [TPL_ROW]
        row = pick_template("saree", "female", culture="tamil", style_tag="festive")
    assert row["template_code"] == "saree_f_01"
    kwargs = m.call_args.kwargs
    assert kwargs["culture"] == "tamil" and kwargs["style_tag"] == "festive"


def test_pick_relaxes_filters_progressively():
    with patch("app.services.template_service.queries.select_templates") as m:
        m.side_effect = [[], [], [TPL_ROW]]  # exact -> culture-only -> loose
        row = pick_template("saree", "female", culture="tamil", style_tag="festive")
    assert row is not None
    assert m.call_count == 3
    last_kwargs = m.call_args_list[-1].kwargs
    assert "culture" not in last_kwargs and "style_tag" not in last_kwargs


def test_pick_returns_none_when_no_templates():
    with patch("app.services.template_service.queries.select_templates", return_value=[]):
        assert pick_template("gown", "female") is None


# ------------------------------------------------------ render_recommendation


def _fake_assets():
    tpl = Image.new("RGB", (60, 90), (150, 60, 40))
    mask = Image.new("L", (60, 90), 0)
    for x in range(15, 45):
        for y in range(20, 80):
            mask.putpixel((x, y), 255)
    return tpl, mask


def test_render_returns_public_url():
    tpl, mask = _fake_assets()
    with patch("app.services.template_service._fetch_image") as mf, patch(
        "app.services.template_service.__name__", "x"
    ), patch("app.db.supabase_client.get_supabase") as msb:
        mf.side_effect = [tpl, mask]
        storage = msb.return_value.storage
        bucket_obj = MagicMock(); bucket_obj.name = "renders"
        storage.list_buckets.return_value = [bucket_obj]
        storage.from_.return_value.get_public_url.return_value = "https://x/renders/r.jpg"
        url = render_recommendation(TPL_ROW, "#0F7B4D")
    assert url == "https://x/renders/r.jpg"


def test_render_cached_second_call_no_work():
    tpl, mask = _fake_assets()
    with patch("app.services.template_service._fetch_image") as mf, patch(
        "app.db.supabase_client.get_supabase"
    ) as msb:
        mf.side_effect = [tpl, mask]
        storage = msb.return_value.storage
        b = MagicMock(); b.name = "renders"
        storage.list_buckets.return_value = [b]
        storage.from_.return_value.get_public_url.return_value = "https://x/renders/r.jpg"
        u1 = render_recommendation(TPL_ROW, "#0F7B4D")
        u2 = render_recommendation(TPL_ROW, "#0F7B4D")
    assert u1 == u2
    assert mf.call_count == 2  # assets fetched once, NOT four times


def test_render_bad_hex_returns_none():
    assert render_recommendation(TPL_ROW, "greenish") is None
    assert render_recommendation(TPL_ROW, "") is None


def test_render_fetch_failure_returns_none():
    with patch("app.services.template_service._fetch_image", return_value=None):
        assert render_recommendation(TPL_ROW, "#0F7B4D") is None
