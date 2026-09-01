"""HueFit MVP - template selection + recoloured recommendation images.

The runtime flow from the strategy document, section 9:
  colour recommendation (LLM) -> select approved template -> fetch template
  image + stored mask -> recolour inside the mask -> final image.

Design:
  - Template + mask files are fetched from their public URLs once and
    cached in memory (they are fixed assets; a server restart re-warms).
  - Recoloured results are cached by (template_code, hex) - deterministic
    output means same input = same image, so we never recolour twice.
  - Recoloured images are uploaded once to the public 'renders' bucket;
    the response carries a permanent URL (same pattern as templates).
  - Every failure degrades gracefully: no template -> image_url None
    (the frontend already handles missing images from the v1 contract).
"""
from __future__ import annotations

import hashlib
import io
import logging
import threading

import requests as http
from PIL import Image

from app.db import queries

log = logging.getLogger(__name__)

RENDER_BUCKET = "renders"

_asset_cache: dict[str, Image.Image] = {}
_render_cache: dict[str, str] = {}  # (code|hex) -> public URL
_select_cache: dict[tuple, tuple[float, dict | None]] = {}  # selection -> (ts, row)
_SELECT_TTL = 300.0  # templates change rarely; 5-min cache kills 4-12 DB
                     # round trips per analyze on the hot path
_lock = threading.Lock()
MAX_RENDER_HEIGHT = 1024  # cap render size: faster recolour, smaller files,
                          # less storage egress - plenty for app display


def _fetch_image(url: str) -> Image.Image | None:
    if url in _asset_cache:
        return _asset_cache[url]
    try:
        resp = http.get(url, timeout=20)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img.load()
        with _lock:
            _asset_cache[url] = img
        return img
    except Exception as exc:
        log.warning("template asset fetch failed: %s (%s)", url[:80], str(exc)[:80])
        return None


def pick_template(
    dress_type: str,
    gender: str,
    culture: str | None = None,
    style_tag: str | None = None,
) -> dict | None:
    """Choose an approved+active template. Relaxes filters progressively:
    exact culture+tag -> culture only -> dress type+gender only.

    Results are cached for a few minutes (the library changes rarely) so
    a 4-outfit analyze costs at most ONE selection query set, not four."""
    import time as _time

    cache_key = (dress_type, gender, culture, style_tag)
    hit = _select_cache.get(cache_key)
    if hit and (_time.monotonic() - hit[0]) < _SELECT_TTL:
        return hit[1]
    row = _pick_template_uncached(dress_type, gender, culture, style_tag)
    with _lock:
        _select_cache[cache_key] = (_time.monotonic(), row)
    return row


def _pick_template_uncached(
    dress_type: str,
    gender: str,
    culture: str | None = None,
    style_tag: str | None = None,
) -> dict | None:
    attempts = [
        {"dress_type": dress_type, "gender": gender, "culture": culture, "style_tag": style_tag},
        {"dress_type": dress_type, "gender": gender, "culture": culture},
        {"dress_type": dress_type, "gender": gender},
    ]
    seen = set()
    for kwargs in attempts:
        key = tuple(sorted((k, v) for k, v in kwargs.items() if v))
        if key in seen:
            continue
        seen.add(key)
        rows = queries.select_templates(**{k: v for k, v in kwargs.items() if v}, limit=3)
        if rows:
            return rows[0]
    return None


def render_recommendation(
    template_row: dict, target_hex: str
) -> str | None:
    """Recolour the template to the target colour; return a public URL.

    Cached: the same template+colour pair is rendered and uploaded once.
    Returns None on any failure (caller falls back gracefully).
    """
    code = template_row.get("template_code", "unknown")
    hex_norm = (target_hex or "").upper().lstrip("#")
    if len(hex_norm) != 6:
        return None
    cache_key = f"{code}|{hex_norm}"
    if cache_key in _render_cache:
        return _render_cache[cache_key]

    template = _fetch_image(template_row.get("image_url", ""))
    mask = _fetch_image(template_row.get("mask_url", ""))
    if template is None or mask is None:
        return None

    # Cap render size: big design-team templates (e.g. 2000x3000) would cost
    # ~10x the pixels for no visual gain at app display sizes.
    if template.height > MAX_RENDER_HEIGHT:
        ratio = MAX_RENDER_HEIGHT / template.height
        new_size = (max(1, int(template.width * ratio)), MAX_RENDER_HEIGHT)
        template = template.resize(new_size, Image.LANCZOS)
        mask = mask.resize(new_size)

    from app.services.recolor_service import recolor_to_bytes

    try:
        data = recolor_to_bytes(template, mask, f"#{hex_norm}")
    except Exception as exc:
        log.warning("recolour failed for %s: %s", cache_key, str(exc)[:80])
        return None

    # upload once to the public renders bucket
    from app.db.supabase_client import get_supabase

    sb = get_supabase()
    digest = hashlib.md5(data).hexdigest()[:10]
    path = f"{code}/{hex_norm}-{digest}.jpg"
    try:
        names = {b.name for b in sb.storage.list_buckets()}
        if RENDER_BUCKET not in names:
            sb.storage.create_bucket(RENDER_BUCKET, options={"public": True})
        try:
            sb.storage.from_(RENDER_BUCKET).upload(
                path, data, file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
        except Exception:
            pass  # already uploaded -> fine
        url = sb.storage.from_(RENDER_BUCKET).get_public_url(path)
    except Exception as exc:
        log.warning("render upload failed: %s", str(exc)[:80])
        return None

    with _lock:
        _render_cache[cache_key] = url
    return url


def clear_caches() -> None:
    """Testing helper."""
    with _lock:
        _asset_cache.clear()
        _render_cache.clear()
        _select_cache.clear()
