"""Phase T1 tests - template library (DB mocked, validation real)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.db import queries

sys.path.insert(0, "scripts")


# ---------------------------------------------------------------- queries


@pytest.fixture()
def sb():
    with patch("app.db.queries.get_supabase") as m:
        client = MagicMock()
        m.return_value = client
        yield client


def _chain(client):
    chain = client.table.return_value
    for method in ("select", "eq", "limit", "insert", "update", "contains"):
        getattr(chain, method).return_value = chain
    return chain


def test_upsert_template_inserts_new(sb):
    chain = _chain(sb)
    empty = MagicMock(); empty.data = []
    created = MagicMock(); created.data = [{"id": "t1", "template_code": "saree_f_01"}]
    chain.execute.side_effect = [empty, created]
    row = queries.upsert_template({"template_code": "saree_f_01", "dress_type": "saree"})
    assert row["id"] == "t1"
    chain.insert.assert_called_once()


def test_upsert_template_updates_existing(sb):
    chain = _chain(sb)
    existing = MagicMock(); existing.data = [{"id": "t9"}]
    updated = MagicMock(); updated.data = [{"id": "t9"}]
    chain.execute.side_effect = [existing, updated]
    row = queries.upsert_template({"template_code": "saree_f_01"})
    assert row["id"] == "t9"
    chain.update.assert_called_once()


def test_select_templates_filters_active_and_approved(sb):
    chain = _chain(sb)
    result = MagicMock(); result.data = [{"template_code": "saree_f_01"}]
    chain.execute.return_value = result
    rows = queries.select_templates(dress_type="saree", gender="female")
    assert rows[0]["template_code"] == "saree_f_01"
    eq_calls = [c.args for c in chain.eq.call_args_list]
    assert ("active_status", True) in eq_calls
    assert ("qa_status", "approved") in eq_calls
    assert ("dress_type", "saree") in eq_calls
    assert ("gender", "female") in eq_calls


def test_set_template_qa(sb):
    chain = _chain(sb)
    result = MagicMock(); result.data = [{"id": "t1"}]
    chain.execute.return_value = result
    assert queries.set_template_qa("saree_f_01", "approved", True) is True
    chain.update.assert_called_once_with({"qa_status": "approved", "active_status": True})


# ----------------------------------------------------- uploader validation


def _pair(folder: Path, code="tpl_01", img_size=(200, 300), mask_size=None,
          mask_mode="binary", coverage=0.3):
    """Create an image+mask pair on disk; returns the CSV row dict."""
    mask_size = mask_size or img_size
    img = Image.new("RGB", img_size, (150, 60, 40))
    img.save(folder / f"{code}.jpg")

    mask = Image.new("L", mask_size, 0)
    if mask_mode == "binary":
        w, h = mask_size
        box_h = int(h * coverage)
        for x in range(w):
            for y in range(box_h):
                mask.putpixel((x, y), 255)
    elif mask_mode == "grey":
        mask = Image.new("L", mask_size, 128)
    mask.save(folder / f"{code}_mask.png")

    return {
        "template_code": code, "dress_type": "saree", "gender": "female",
        "culture": "tamil", "image_file": f"{code}.jpg",
        "mask_file": f"{code}_mask.png",
    }


def test_validate_pair_accepts_good(tmp_path):
    from upload_templates import validate_pair

    row = _pair(tmp_path)
    problems, info = validate_pair(row, tmp_path, 2)
    assert problems == []
    assert 0.25 < info["coverage"] < 0.35


def test_validate_pair_rejects_size_mismatch(tmp_path):
    from upload_templates import validate_pair

    row = _pair(tmp_path, code="tpl_02", mask_size=(100, 100))
    problems, _ = validate_pair(row, tmp_path, 2)
    assert any("size mismatch" in p for p in problems)


def test_validate_pair_rejects_grey_mask(tmp_path):
    from upload_templates import validate_pair

    row = _pair(tmp_path, code="tpl_03", mask_mode="grey")
    problems, _ = validate_pair(row, tmp_path, 2)
    assert any("not binary" in p for p in problems)


def test_validate_pair_rejects_empty_mask(tmp_path):
    from upload_templates import validate_pair

    row = _pair(tmp_path, code="tpl_04", coverage=0.01)
    problems, _ = validate_pair(row, tmp_path, 2)
    assert any("empty" in p for p in problems)


def test_validate_pair_rejects_inverted_mask(tmp_path):
    from upload_templates import validate_pair

    row = _pair(tmp_path, code="tpl_05", coverage=0.95)
    problems, _ = validate_pair(row, tmp_path, 2)
    assert any("inverted" in p for p in problems)


def test_validate_pair_rejects_bad_metadata(tmp_path):
    from upload_templates import validate_pair

    row = _pair(tmp_path, code="tpl_06")
    row["gender"] = "alien"
    row["culture"] = "mars"
    row["dress_type"] = ""
    problems, _ = validate_pair(row, tmp_path, 2)
    assert len(problems) == 3
