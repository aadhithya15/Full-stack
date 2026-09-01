"""HueFit MVP - garment recolouring engine.

Takes: template image + its QA-approved mask + a target colour.
Returns: the template with ONLY the garment recoloured, texture preserved.

How it works (deterministic pixel math - no AI, no network, ~60ms):
  1. Garment pixels keep their per-pixel BRIGHTNESS (this preserves folds,
     shadows, drape lines and fabric texture).
  2. Hue and saturation are replaced with the target colour's.
  3. A clamped brightness gain shifts the garment's average brightness
     toward the target colour's lightness (dark targets look dark,
     pastels look pastel - without crushing texture).
  4. Composite through a lightly feathered mask so the recolour edge
     blends naturally against skin/background.

Same template + same colour = identical output every time (cacheable).
"""
from __future__ import annotations

import colorsys
import io

import numpy as np
from PIL import Image, ImageFilter


def _hex_to_rgb(hexcode: str) -> tuple[int, int, int]:
    h = (hexcode or "").lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad hex colour: {hexcode!r}")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def recolor_garment(
    template: Image.Image,
    mask: Image.Image,
    target_hex: str,
    strength: float = 1.0,
) -> Image.Image:
    """Recolour the masked garment region to the target colour.

    strength 1.0 = full recolour; lower blends with the original.
    """
    tr, tg, tb = _hex_to_rgb(target_hex)
    t_h, t_s, t_v = colorsys.rgb_to_hsv(tr / 255, tg / 255, tb / 255)

    base = template.convert("RGB")
    m = mask.convert("L")
    if m.size != base.size:
        m = m.resize(base.size)

    img = np.asarray(base, dtype=np.float32) / 255.0
    msel = (np.asarray(m, dtype=np.float32) / 255.0) > 0.5
    if not msel.any():
        return base  # empty mask -> nothing to recolour

    # per-pixel brightness (HSV value = max channel)
    v = img.max(axis=2)
    avg_v = float(v[msel].mean())
    gain = t_v / avg_v if avg_v > 0.05 else 1.0
    gain = max(0.35, min(gain, 1.8))  # clamp: never blow out or crush texture
    nv = np.clip(v * gain, 0.0, 1.0)

    # HSV -> RGB with FIXED hue+saturation, per-pixel value (closed form)
    sector = int(t_h * 6) % 6
    f = t_h * 6 - int(t_h * 6)
    p_, q_, t_ = 1 - t_s, 1 - f * t_s, 1 - (1 - f) * t_s
    combo = {
        0: (1.0, t_, p_), 1: (q_, 1.0, p_), 2: (p_, 1.0, t_),
        3: (p_, q_, 1.0), 4: (t_, p_, 1.0), 5: (1.0, p_, q_),
    }[sector]
    recoloured = np.stack([nv * combo[0], nv * combo[1], nv * combo[2]], axis=2)

    out = img.copy()
    if strength >= 1.0:
        out[msel] = recoloured[msel]
    else:
        out[msel] = recoloured[msel] * strength + img[msel] * (1.0 - strength)

    out_img = Image.fromarray((out * 255).astype(np.uint8))
    soft = m.filter(ImageFilter.GaussianBlur(1))
    return Image.composite(out_img, base, soft)


def recolor_to_bytes(
    template: Image.Image, mask: Image.Image, target_hex: str, quality: int = 88
) -> bytes:
    """Recolour and return JPEG bytes (for upload/response)."""
    result = recolor_garment(template, mask, target_hex)
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
