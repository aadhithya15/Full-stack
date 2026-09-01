"""Phase V2-2 tests - colour extraction (real) + clip service (mocked).

The colour extractor runs for real (pure Pillow math - fast, no model).
CLIP itself is NOT loaded in tests (600MB model, slow) - the service's
lazy-loading contract is tested with mocks instead. Real CLIP is verified
live via scripts/index_catalogue.py --dry-run and check_clip.py.
"""
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.color_extract import extract_dominant

# ------------------------------------------------------------ colour extract


def _img(rgb, size=(120, 160)):
    return Image.new("RGB", size, rgb)


def test_maroon_classified():
    hexcode, family = extract_dominant(_img((151, 57, 34)))
    assert family in ("maroon-red", "orange-rust")
    assert hexcode.startswith("#")


def test_gold_classified():
    _, family = extract_dominant(_img((201, 162, 75)))
    assert family == "yellow-gold"


def test_navy_classified():
    _, family = extract_dominant(_img((31, 53, 84)))
    assert family == "blue"


def test_black_classified():
    _, family = extract_dominant(_img((20, 20, 22)))
    assert family == "black"


def test_cream_classified():
    _, family = extract_dominant(_img((244, 240, 229)))
    assert family == "white-cream"


def test_background_ignored():
    """A maroon garment on a white background must classify as maroon."""
    img = Image.new("RGB", (100, 100), (250, 250, 250))
    for x in range(30, 70):
        for y in range(20, 90):
            img.putpixel((x, y), (150, 40, 30))
    _, family = extract_dominant(img)
    assert family == "maroon-red"


# ------------------------------------------------------------- clip service


def test_clip_lazy_load_called_once():
    from app.services import clip_service

    fake_state = {
        "model": MagicMock(),
        "preprocess": MagicMock(),
        "tokenizer": MagicMock(),
        "torch": MagicMock(),
    }
    with patch.object(clip_service, "_load", return_value=fake_state) as ml:
        # encode_text path: model.encode_text -> normalized tensor
        feats = MagicMock()
        feats.norm.return_value = feats
        feats.__truediv__ = lambda self, o: feats
        row = MagicMock()
        row.tolist.return_value = [0.1] * 512
        feats.__getitem__ = lambda self, i: row
        fake_state["model"].encode_text.return_value = feats

        out = clip_service.embed_text("maroon saree")
        assert len(out) == 512
        ml.assert_called_once()


def test_model_info_reports_config():
    from app.services.clip_service import model_info

    info = model_info()
    assert "model" in info and "pretrained" in info


# ------------------------------------------------------- indexer validation


def test_indexer_validation_catches_bad_rows(tmp_path):
    import sys
    sys.path.insert(0, "scripts")
    from index_catalogue import validate

    folder = tmp_path
    (folder / "images").mkdir()
    (folder / "images" / "ok.jpg").write_bytes(b"x")

    good = {"title": "T", "gender": "female", "culture": "tamil", "image_file": "ok.jpg"}
    assert validate(good, folder, 2) == []

    bad = {"title": "", "gender": "alien", "culture": "mars", "image_file": "missing.jpg"}
    problems = validate(bad, folder, 3)
    assert len(problems) == 4  # title, gender, culture, image all wrong
