"""Template selection, skin-tone variants, recolouring, and render upload.

Runtime flow:
  1. Select an approved outfit template.
  2. Select the model photo matching the canonical user skin tone.
  3. Recolour every available garment mask with the AI colours.
  4. Upload one deterministic render and return its permanent public URL.

Any image-side failure degrades to an existing template photo where possible;
it never breaks the fashion recommendation itself.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests as http
from PIL import Image

from app.db import queries
from app.services.skin_tone_service import canonical_tone

log = logging.getLogger(__name__)

RENDER_BUCKET = "renders"
MAX_RENDER_HEIGHT = 1024
_SELECT_TTL = 300.0
_UPLOAD_ATTEMPTS = 3

try:
    _LANCZOS = Image.Resampling.LANCZOS
    _NEAREST = Image.Resampling.NEAREST
except AttributeError:  # Pillow < 9.1 compatibility
    _LANCZOS = Image.LANCZOS
    _NEAREST = Image.NEAREST

_asset_cache: dict[str, Image.Image] = {}
_render_cache: dict[str, str] = {}
_select_cache: dict[tuple, tuple[float, dict | None]] = {}
_cache_lock = threading.Lock()
_upload_lock = threading.Lock()

_HEX_RE = re.compile(r"^[0-9A-F]{6}$")

# Public/API labels remain stable while the latest template set stores six
# calibrated native depth variants. An undertone-only request has no reliable
# depth, so warm uses the warm-light native and cool uses the safe middle depth.
PUBLIC_TO_NATIVE_TONE = {
    "fair": "fair",
    "light": "light-warm",
    "wheatish": "light-tan",
    "medium": "medium-brown",
    "dusky": "deep",
    "deep": "ebony",
    "warm": "light-warm",
    "cool": "medium-brown",
}

_LOCAL_FILE_PREFIX = "local-file:"


def _local_catalog_enabled() -> bool:
    return os.getenv("HUEFIT_LOCAL_CATALOG_TEST", "").strip() == "1"


def _local_catalog_rows() -> tuple[Path, list[dict]]:
    catalog_text = os.getenv("HUEFIT_LOCAL_CATALOG_FILE", "").strip()
    if not catalog_text:
        raise ValueError("HUEFIT_LOCAL_CATALOG_FILE is not set")
    catalog_path = Path(catalog_text).resolve()
    value = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = value.get("templates") if isinstance(value, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("local catalog has no templates")
    return catalog_path, rows


def _expand_local_row(catalog_path: Path, value: dict) -> dict:
    row = dict(value)
    root = catalog_path.parent

    def local_url(name: Any) -> str | None:
        text = str(name or "").strip()
        if not text:
            return None
        path = (root / Path(text)).resolve()
        if not path.is_file():
            raise ValueError(f"local catalog asset is missing: {path}")
        return _LOCAL_FILE_PREFIX + str(path)

    row["image_url"] = local_url(row.pop("image_file", ""))
    row["mask_url"] = local_url(row.pop("mask_file", ""))
    row["mask2_url"] = local_url(row.pop("mask2_file", ""))
    row["mask3_url"] = local_url(row.pop("mask3_file", ""))
    tones = row.get("tone_variants") or {}
    if not isinstance(tones, dict):
        tones = {}
    row["tone_variants"] = {
        str(tone): local_url(name)
        for tone, name in tones.items()
        if name
    }
    return row


def _local_template_row(
    dress_type: str,
    gender: str,
    culture: str | None,
    style_tag: str | None,
) -> dict | None:
    """Select from all locally installed templates in explicit demo mode."""
    if not _local_catalog_enabled():
        return None
    try:
        catalog_path, rows = _local_catalog_rows()
        gender_rows = [
            row
            for row in rows
            if gender == "unisex" or str(row.get("gender")) in (gender, "unisex")
        ]
        if not gender_rows:
            gender_rows = rows
        exact = [row for row in gender_rows if str(row.get("dress_type")) == dress_type]
        candidates = exact
        if not candidates and culture:
            candidates = [
                row for row in gender_rows if str(row.get("culture")) == culture
            ]
        if not candidates and style_tag:
            candidates = [
                row
                for row in gender_rows
                if style_tag in (row.get("style_tags") or [])
            ]
        if not candidates:
            candidates = gender_rows
        if not candidates:
            return None
        return _expand_local_row(catalog_path, candidates[0])
    except Exception as exc:
        log.warning("local catalog selection failed: %s", str(exc)[:160])
        return None


def _save_local_render(path: str, data: bytes) -> str | None:
    try:
        static_folder = Path(__file__).resolve().parents[1] / "static" / "local-template-renders"
        static_folder.mkdir(parents=True, exist_ok=True)
        name = Path(path).name
        (static_folder / name).write_bytes(data)
        base_url = os.getenv("HUEFIT_LOCAL_BASE_URL", "http://localhost:5000").rstrip("/")
        return f"{base_url}/static/local-template-renders/{name}"
    except Exception as exc:
        log.warning("local render save failed: %s", str(exc)[:120])
        return None


def _fetch_image(url: str) -> Image.Image | None:
    """Fetch a public asset, or open an explicit local-catalog asset."""
    if not url:
        return None
    if url.startswith(_LOCAL_FILE_PREFIX):
        try:
            image = Image.open(url[len(_LOCAL_FILE_PREFIX) :])
            image.load()
            return image
        except Exception as exc:
            log.warning("local template asset failed: %s", str(exc)[:120])
            return None
    cached = _asset_cache.get(url)
    if cached is not None:
        return cached.copy()
    try:
        response = http.get(url, timeout=20)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        image.load()
        with _cache_lock:
            _asset_cache[url] = image.copy()
        return image
    except Exception as exc:
        log.warning("template asset fetch failed: %s (%s)", url[:100], str(exc)[:100])
        return None


def _normalize_dress_type(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    aliases = (
        "formal-shirt-pants",
        "shirt-trousers",
        "three-piece-suit",
        "two-piece-suit",
        "kurta-jacket-tapered",
        "kurta-pajama",
        "kurta-dhoti",
        "blazer-chinos",
        "nehru-jacket",
        "pathani-suit",
        "polo-jeans",
        "casual-coord",
        "lehenga-choli",
        "salwar-suit",
        "kurta-palazzo",
        "floor-length-gown",
        "maxi-dress",
        "midi-dress",
        "skirt-blouse",
        "blazer-trousers",
        "western-coord",
        "jeans-top",
        "sherwani",
        "bandhgala",
        "tuxedo",
        "saree",
        "anarkali",
        "sharara",
        "gharara",
        "jumpsuit",
        "kaftan",
        "gown",
    )
    if text in aliases:
        return text
    for alias in aliases:
        if alias in text:
            return alias
    # Common recommendation wording that does not exactly match catalog ids.
    keyword_aliases = {
        "saree": "saree",
        "lehenga": "lehenga-choli",
        "anarkali": "anarkali",
        "palazzo": "kurta-palazzo",
        "sharara": "sharara",
        "gharara": "gharara",
        "sherwani": "sherwani",
        "bandhgala": "bandhgala",
        "pathani": "pathani-suit",
        "tuxedo": "tuxedo",
        "jumpsuit": "jumpsuit",
        "kaftan": "kaftan",
        "veshti": "kurta-dhoti",
        "dhoti": "kurta-dhoti",
        "kurta-pyjama": "kurta-pajama",
        "kurta-pajama": "kurta-pajama",
        "nehru": "nehru-jacket",
        "salwar": "salwar-suit",
        "floor-length": "floor-length-gown",
        "maxi": "maxi-dress",
        "midi": "midi-dress",
        "kurta-jacket": "kurta-jacket-tapered",
        "asymmetric-hem": "kurta-jacket-tapered",
    }
    for keyword, alias in keyword_aliases.items():
        if keyword in text:
            return alias
    return text


def pick_template(
    dress_type: str,
    gender: str,
    culture: str | None = None,
    style_tag: str | None = None,
) -> dict | None:
    """Choose an approved template, progressively relaxing filters."""
    normalized = _normalize_dress_type(dress_type)
    cache_key = (normalized, gender, culture, style_tag)
    hit = _select_cache.get(cache_key)
    if hit and time.monotonic() - hit[0] < _SELECT_TTL:
        return hit[1]

    row = _pick_template_uncached(normalized, gender, culture, style_tag)
    with _cache_lock:
        _select_cache[cache_key] = (time.monotonic(), row)
    return row


def _pick_template_uncached(
    dress_type: str,
    gender: str,
    culture: str | None = None,
    style_tag: str | None = None,
) -> dict | None:
    local_row = _local_template_row(dress_type, gender, culture, style_tag)
    if local_row is not None:
        return local_row
    attempts = [
        {"dress_type": dress_type, "gender": gender, "culture": culture, "style_tag": style_tag},
        {"dress_type": dress_type, "gender": gender, "culture": culture},
        {"dress_type": dress_type, "gender": gender},
        {"gender": gender, "culture": culture},
        {"gender": gender},
    ]
    seen: set[tuple] = set()
    for values in attempts:
        kwargs = {key: value for key, value in values.items() if value}
        key = tuple(sorted(kwargs.items()))
        if key in seen:
            continue
        seen.add(key)
        rows = queries.select_templates(**kwargs, limit=3)
        if rows:
            return rows[0]
    return None


def _normalize_colours(colours: Any) -> list[str]:
    """Accept a hex string, dress_colors objects, or a list of hex strings."""
    if isinstance(colours, str):
        values = [colours]
    elif isinstance(colours, (list, tuple)):
        values = list(colours)
    else:
        values = []

    result: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("hex")
        normalized = str(value or "").strip().upper().lstrip("#")
        if _HEX_RE.fullmatch(normalized):
            result.append("#" + normalized)
    return result[:3]


def _tone_variant_map(template_row: dict) -> dict[str, str]:
    value = template_row.get("tone_variants") or {}
    if isinstance(value, str):
        try:
            import json

            value = json.loads(value)
        except Exception:
            value = {}
    if not isinstance(value, dict):
        return {}
    return {
        str(key).lower(): str(url)
        for key, url in value.items()
        if key and isinstance(url, str) and url
    }


def _variant_tone_key(
    template_row: dict,
    requested_tone: str | None,
) -> str | None:
    """Resolve a public tone to a latest native key, with legacy fallback."""
    public_tone = canonical_tone(requested_tone)
    if not public_tone:
        return None
    variants = _tone_variant_map(template_row)
    native_tone = PUBLIC_TO_NATIVE_TONE.get(public_tone)
    if native_tone in variants:
        return native_tone
    # Rows uploaded from the earlier eight-folder drop used public keys.
    if public_tone in variants:
        return public_tone
    return None


def _choose_template_image(
    template_row: dict,
    requested_tone: str | None,
) -> tuple[Image.Image | None, str, str]:
    """Return image, public source URL, and actual native tone (or base)."""
    base_url = str(template_row.get("image_url") or "")
    tone_key = _variant_tone_key(template_row, requested_tone)
    variants = _tone_variant_map(template_row)
    variant_url = variants.get(tone_key or "")

    if variant_url:
        variant = _fetch_image(variant_url)
        if variant is not None:
            return variant, variant_url, tone_key or "base"
        log.warning("tone variant unavailable for %s; using base", tone_key)

    base = _fetch_image(base_url)
    return base, base_url, "base"


def _object_name(item: Any) -> str | None:
    if isinstance(item, dict):
        return item.get("name")
    return getattr(item, "name", None)


def _object_exists(bucket: Any, path: str) -> bool | None:
    """Verify an object by listing its exact storage folder.

    None means the SDK response could not be interpreted (mainly test mocks).
    Real Supabase clients return a list and therefore get strict verification.
    """
    folder, name = path.rsplit("/", 1) if "/" in path else ("", path)
    try:
        items = bucket.list(folder)
    except Exception:
        return False
    if not isinstance(items, list):
        return None
    return any(_object_name(item) == name for item in items)


def _ensure_render_bucket(storage: Any) -> None:
    buckets = storage.list_buckets()
    names = {_object_name(bucket) for bucket in buckets}
    if RENDER_BUCKET not in names:
        storage.create_bucket(RENDER_BUCKET, options={"public": True})


def _upload_render(path: str, data: bytes) -> str | None:
    """Save locally in demo mode; otherwise upload normally to Supabase."""
    if _local_catalog_enabled():
        return _save_local_render(path, data)

    from app.db.supabase_client import get_supabase

    with _upload_lock:
        try:
            storage = get_supabase().storage
            _ensure_render_bucket(storage)
            bucket = storage.from_(RENDER_BUCKET)
        except Exception as exc:
            log.warning("render storage setup failed: %s", str(exc)[:120])
            return None

        for attempt in range(1, _UPLOAD_ATTEMPTS + 1):
            upload_ok = False
            try:
                bucket.upload(
                    path,
                    data,
                    file_options={"content-type": "image/jpeg", "upsert": "true"},
                )
                upload_ok = True
            except Exception as exc:
                log.warning(
                    "render upload attempt %d failed for %s: %s",
                    attempt,
                    path,
                    str(exc)[:100],
                )

            exists = _object_exists(bucket, path)
            if exists is True or (exists is None and upload_ok):
                try:
                    return bucket.get_public_url(path)
                except Exception as exc:
                    log.warning("public render URL failed: %s", str(exc)[:100])
            if attempt < _UPLOAD_ATTEMPTS:
                time.sleep(0.15 * attempt)

    return None


def render_recommendation(
    template_row: dict,
    colours: Any,
    skin_tone: str | None = None,
) -> str | None:
    """Render all garment masks on the matching skin-tone model photo.

    The old one-colour call remains supported. If recolouring or upload fails
    after the tone photo was fetched, its existing public URL is returned as
    a usable visual fallback.
    """
    normalized_colours = _normalize_colours(colours)
    if not normalized_colours:
        return None

    code = str(template_row.get("template_code") or "unknown")
    requested_tone = canonical_tone(skin_tone)
    predicted_tone = _variant_tone_key(template_row, requested_tone) or "base"
    colour_key = "-".join(colour[1:] for colour in normalized_colours)
    cache_key = f"{code}|{predicted_tone}|{colour_key}"
    cached = _render_cache.get(cache_key)
    if cached:
        return cached

    template, source_url, actual_tone = _choose_template_image(template_row, requested_tone)
    if template is None:
        return None

    mask_urls = [
        template_row.get("mask_url"),
        template_row.get("mask2_url"),
        template_row.get("mask3_url"),
    ]
    masks: list[Image.Image] = []
    for url in mask_urls:
        if not url:
            continue
        mask = _fetch_image(str(url))
        if mask is not None:
            masks.append(mask)

    # A tone-matched photo is still a useful visual if all masks fail.
    if not masks:
        if source_url:
            fallback_key = f"{code}|{actual_tone}|{colour_key}"
            with _cache_lock:
                _render_cache[fallback_key] = source_url
                if actual_tone == predicted_tone:
                    _render_cache[cache_key] = source_url
            return source_url
        return None

    if template.height > MAX_RENDER_HEIGHT:
        ratio = MAX_RENDER_HEIGHT / template.height
        target_size = (max(1, round(template.width * ratio)), MAX_RENDER_HEIGHT)
        template = template.resize(target_size, _LANCZOS)
        masks = [mask.resize(target_size, _NEAREST) for mask in masks]

    from app.services.recolor_service import recolor_many_to_bytes

    try:
        data = recolor_many_to_bytes(template, masks, normalized_colours)
    except Exception as exc:
        log.warning("recolour failed for %s: %s", cache_key, str(exc)[:100])
        return source_url or None

    digest = hashlib.md5(data).hexdigest()[:12]
    path = f"{code}/{actual_tone}/{colour_key}-{digest}.jpg"
    url = _upload_render(path, data)
    if not url:
        return source_url or None

    # The variant chosen after fetch may differ from the predicted cache tone
    # when a broken variant falls back to base.
    final_key = f"{code}|{actual_tone}|{colour_key}"
    with _cache_lock:
        _render_cache[final_key] = url
        if actual_tone == predicted_tone:
            _render_cache[cache_key] = url
    return url


def clear_caches() -> None:
    """Clear process caches (used by tests and after template administration)."""
    with _cache_lock:
        _asset_cache.clear()
        _render_cache.clear()
        _select_cache.clear()
