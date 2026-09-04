"""Skin-tone template variants, multi-mask rendering, and gap defense."""
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

from app.services import template_service
from app.services.recolor_service import repair_mask, repair_mask_set
from app.services.skin_tone_service import CANONICAL_TONES, canonical_tone


@pytest.fixture(autouse=True)
def _fresh_caches():
    template_service.clear_caches()
    yield
    template_service.clear_caches()


def _mask(size=(80, 80), box=(10, 10, 35, 70)):
    image = Image.new("L", size, 0)
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            image.putpixel((x, y), 255)
    return image


def _row(**extra):
    return {
        "template_code": "tone_test_01",
        "image_url": "https://x/base.jpg",
        "mask_url": "https://x/mask1.png",
        **extra,
    }


def test_all_eight_canonical_labels_map_directly():
    assert tuple(canonical_tone(tone) for tone in CANONICAL_TONES) == CANONICAL_TONES


def test_specific_depth_beats_warm_or_cool_undertone():
    assert canonical_tone("warm wheatish with golden undertones") == "wheatish"
    assert canonical_tone("cool deep skin") == "deep"
    assert canonical_tone("deep brown skin") == "deep"
    assert canonical_tone(None) is None


def test_canonical_aliases_are_word_safe():
    assert canonical_tone("porcelain complexion") == "fair"
    assert canonical_tone("golden undertone") == "warm"
    assert canonical_tone("highlighted hair") is None


def test_tiny_mask_hole_and_one_pixel_gap_are_closed():
    mask = _mask(size=(15, 15), box=(3, 3, 12, 12))
    mask.putpixel((7, 7), 0)
    mask.putpixel((7, 6), 0)
    fixed = repair_mask(mask)
    assert fixed.getpixel((7, 7)) == 255
    assert fixed.getpixel((7, 6)) == 255
    assert fixed.getpixel((0, 0)) == 0


def test_render_fetches_selected_tone_variant_first():
    row = _row(tone_variants={"dusky": "https://x/dusky.jpg"})
    template = Image.new("RGB", (80, 80), (150, 80, 50))
    with patch("app.services.template_service._fetch_image") as fetch, patch(
        "app.services.template_service._upload_render", return_value="https://x/render.jpg"
    ):
        fetch.side_effect = [template, _mask()]
        result = template_service.render_recommendation(row, "#0F7B4D", "dusky")
    assert result == "https://x/render.jpg"
    assert fetch.call_args_list[0].args[0] == "https://x/dusky.jpg"


def test_broken_tone_variant_falls_back_to_base():
    row = _row(tone_variants={"fair": "https://x/fair.jpg"})
    base = Image.new("RGB", (80, 80), (150, 80, 50))
    with patch("app.services.template_service._fetch_image") as fetch, patch(
        "app.services.template_service._upload_render", return_value="https://x/base-render.jpg"
    ):
        fetch.side_effect = [None, base, _mask()]
        result = template_service.render_recommendation(row, ["#0F7B4D"], "fair")
    assert result == "https://x/base-render.jpg"
    assert fetch.call_args_list[0].args[0] == "https://x/fair.jpg"
    assert fetch.call_args_list[1].args[0] == "https://x/base.jpg"


def test_every_available_mask_receives_an_ai_colour():
    row = _row(mask2_url="https://x/mask2.png")
    template = Image.new("RGB", (80, 80), (130, 110, 90))
    first = _mask(box=(5, 10, 35, 70))
    second = _mask(box=(45, 10, 75, 70))
    captured = {}

    def capture(path, data):
        captured["path"] = path
        captured["data"] = data
        return "https://x/two-colour.jpg"

    with patch("app.services.template_service._fetch_image") as fetch, patch(
        "app.services.template_service._upload_render", side_effect=capture
    ):
        fetch.side_effect = [template, first, second]
        result = template_service.render_recommendation(
            row, ["#E02020", "#2040E0"], None
        )

    rendered = Image.open(BytesIO(captured["data"])).convert("RGB")
    red_pixel = rendered.getpixel((20, 40))
    blue_pixel = rendered.getpixel((60, 40))
    assert result == "https://x/two-colour.jpg"
    assert red_pixel[0] > red_pixel[1] and red_pixel[0] > red_pixel[2]
    assert blue_pixel[2] > blue_pixel[0] and blue_pixel[2] > blue_pixel[1]


def test_render_cache_is_separate_for_each_skin_tone():
    row = _row(
        tone_variants={
            "fair": "https://x/fair.jpg",
            "deep": "https://x/deep.jpg",
        }
    )
    template = Image.new("RGB", (80, 80), (150, 80, 50))
    with patch("app.services.template_service._fetch_image") as fetch, patch(
        "app.services.template_service._upload_render",
        side_effect=["https://x/fair-render.jpg", "https://x/deep-render.jpg"],
    ) as upload:
        fetch.side_effect = [template, _mask(), template, _mask()]
        fair_1 = template_service.render_recommendation(row, "#0F7B4D", "fair")
        deep = template_service.render_recommendation(row, "#0F7B4D", "deep")
        fair_2 = template_service.render_recommendation(row, "#0F7B4D", "fair")

    assert fair_1 == fair_2 == "https://x/fair-render.jpg"
    assert deep == "https://x/deep-render.jpg"
    assert upload.call_count == 2
    assert "/fair/" in upload.call_args_list[0].args[0]
    assert "/deep/" in upload.call_args_list[1].args[0]


@pytest.mark.parametrize(
    ("public_tone", "native_tone"),
    [
        ("fair", "fair"),
        ("light", "light-warm"),
        ("wheatish", "light-tan"),
        ("medium", "medium-brown"),
        ("dusky", "deep"),
        ("deep", "ebony"),
        ("warm", "light-warm"),
        ("cool", "medium-brown"),
    ],
)
def test_public_tone_aliases_select_latest_native_variant(public_tone, native_tone):
    variants = {
        tone: f"https://x/{tone}.jpg"
        for tone in {"fair", "light-warm", "light-tan", "medium-brown", "deep", "ebony"}
    }
    assert template_service._variant_tone_key(
        _row(tone_variants=variants), public_tone
    ) == native_tone


def test_valid_exact_mask_set_passes_through_pixel_for_pixel():
    first = _mask(size=(15, 15), box=(2, 2, 7, 13))
    second = _mask(size=(15, 15), box=(8, 2, 13, 13))
    first.putpixel((4, 6), 0)
    cleaned = repair_mask_set([first, second], first.size)
    assert cleaned[0].tobytes() == first.tobytes()
    assert cleaned[1].tobytes() == second.tobytes()


def test_mask_set_repair_rejects_competing_gap_ownership():
    first = _mask(size=(15, 15), box=(2, 2, 6, 12))
    second = _mask(size=(15, 15), box=(9, 2, 13, 12))
    # One harmless antialiased zero marks this synthetic collection malformed,
    # activating the fallback path under test.
    first.putpixel((0, 0), 1)
    disputed = (7, 7)
    repaired_first = first.copy()
    repaired_second = second.copy()
    repaired_first.putpixel(disputed, 255)
    repaired_second.putpixel(disputed, 255)

    with patch(
        "app.services.recolor_service.repair_mask",
        side_effect=[repaired_first, repaired_second],
    ):
        cleaned = repair_mask_set([first, second], first.size)

    assert cleaned[0].getpixel(disputed) == 0
    assert cleaned[1].getpixel(disputed) == 0
    assert cleaned[0].getpixel((3, 5)) == 255
    assert cleaned[1].getpixel((10, 5)) == 255
