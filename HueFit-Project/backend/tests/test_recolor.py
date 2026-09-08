"""Phase T2 tests - the recolouring engine (pure pixel math, all real)."""
import io

import pytest
from PIL import Image

from app.services.recolor_service import _hex_to_rgb, recolor_garment, recolor_to_bytes


def _template_and_mask(garment_rgb=(150, 60, 40), size=(80, 120)):
    """Small scene: garment block in the middle, skin block above, bg around."""
    img = Image.new("RGB", size, (240, 238, 233))          # background
    mask = Image.new("L", size, 0)
    for x in range(30, 50):
        for y in range(10, 30):
            img.putpixel((x, y), (224, 172, 138))          # 'skin' - NOT masked
    for x in range(20, 60):
        for y in range(40, 110):
            # vertical texture: alternate darker columns
            c = garment_rgb if x % 4 else tuple(max(0, v - 30) for v in garment_rgb)
            img.putpixel((x, y), c)
            mask.putpixel((x, y), 255)
    return img, mask


def _avg_in_region(img, xs, ys):
    px = img.load()
    vals = [px[x, y] for x in xs for y in ys]
    n = len(vals)
    return tuple(sum(v[i] for v in vals) / n for i in range(3))


def test_hex_parsing():
    assert _hex_to_rgb("#0F7B4D") == (15, 123, 77)
    assert _hex_to_rgb("800000") == (128, 0, 0)
    with pytest.raises(ValueError):
        _hex_to_rgb("#12")


def test_garment_becomes_target_hue():
    img, mask = _template_and_mask()
    out = recolor_garment(img, mask, "#0F7B4D")  # emerald
    r, g, b = _avg_in_region(out, range(25, 55), range(50, 100))
    assert g > r and g > b, f"expected green dominant, got {(r, g, b)}"


def test_skin_untouched():
    img, mask = _template_and_mask()
    out = recolor_garment(img, mask, "#0F7B4D")
    before = _avg_in_region(img, range(32, 48), range(14, 26))
    after = _avg_in_region(out, range(32, 48), range(14, 26))
    for b, a in zip(before, after):
        assert abs(b - a) < 6, "skin region changed"


def test_background_untouched():
    img, mask = _template_and_mask()
    out = recolor_garment(img, mask, "#2B4C9B")
    before = _avg_in_region(img, range(0, 10), range(0, 10))
    after = _avg_in_region(out, range(0, 10), range(0, 10))
    for b, a in zip(before, after):
        assert abs(b - a) < 6, "background changed"


def test_texture_preserved():
    """The darker texture columns must remain darker after recolouring."""
    img, mask = _template_and_mask()
    out = recolor_garment(img, mask, "#2B4C9B")
    px = out.load()
    normal = px[26, 70]     # x%4 != 0 column
    dark = px[28, 70]       # x%4 == 0 column (darker in source)
    assert sum(dark) < sum(normal), "texture flattened - dark folds lost"


def test_dark_target_darker_than_light_target():
    img, mask = _template_and_mask()
    dark_out = recolor_garment(img, mask, "#3A0D0D")
    light_out = recolor_garment(img, mask, "#F2C4CE")
    dsum = sum(_avg_in_region(dark_out, range(25, 55), range(50, 100)))
    lsum = sum(_avg_in_region(light_out, range(25, 55), range(50, 100)))
    assert dsum < lsum, "brightness adaptation not working"


def test_deterministic():
    img, mask = _template_and_mask()
    a = recolor_garment(img, mask, "#800000").tobytes()
    b = recolor_garment(img, mask, "#800000").tobytes()
    assert a == b, "same input must give identical output (cacheable)"


def test_empty_mask_returns_original():
    img, _ = _template_and_mask()
    empty = Image.new("L", img.size, 0)
    out = recolor_garment(img, empty, "#800000")
    assert out.tobytes() == img.convert("RGB").tobytes()


def test_mask_resized_if_needed():
    img, mask = _template_and_mask()
    small_mask = mask.resize((40, 60))
    out = recolor_garment(img, small_mask, "#0F7B4D")
    assert out.size == img.size


def test_bytes_output_is_jpeg():
    img, mask = _template_and_mask()
    data = recolor_to_bytes(img, mask, "#0F7B4D")
    assert data[:2] == b"\xff\xd8"  # JPEG magic
    reopened = Image.open(io.BytesIO(data))
    assert reopened.size == img.size
