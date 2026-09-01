"""Dominant-colour extraction for catalogue photos.

Produces the two colour fields the ranking law uses:
  dominant_hex  - '#973922'
  hue_family    - 'maroon-red' (the bucket the colour law scores)

Method: shrink image, ignore near-white/near-black background pixels,
average the remaining colour mass, then classify hue into named families.
Client-provided colour metadata always wins over this extractor (it is the
fallback, per the plan).
"""
from __future__ import annotations

import colorsys

# hue (degrees) -> family name; order matters (first match wins)
_FAMILIES = [
    ((0, 14), "maroon-red"),
    ((14, 40), "orange-rust"),
    ((40, 70), "yellow-gold"),
    ((70, 165), "green-olive"),
    ((165, 200), "teal-cyan"),
    ((200, 255), "blue"),
    ((255, 290), "purple-violet"),
    ((290, 335), "pink-magenta"),
    ((335, 361), "maroon-red"),
]


def _family_for_hsv(h_deg: float, s: float, v: float) -> str:
    if v < 0.16:
        return "black"
    if s < 0.12:
        return "white-cream" if v > 0.82 else "grey"
    if s < 0.35 and v > 0.55 and 15 <= h_deg <= 50:
        return "beige-brown"
    for (lo, hi), name in _FAMILIES:
        if lo <= h_deg < hi:
            # dark warm reds/oranges read as brown
            if name in ("orange-rust",) and v < 0.45:
                return "beige-brown"
            return name
    return "grey"


def extract_dominant(image) -> tuple[str, str]:
    """PIL Image -> (dominant_hex, hue_family)."""
    img = image.convert("RGB")
    img.thumbnail((96, 96))
    pixels = list(img.getdata())

    # drop background-ish pixels (near-white / near-black edges of product shots)
    keep = []
    for r, g, b in pixels:
        mx, mn = max(r, g, b), min(r, g, b)
        if mx > 242 and mn > 225:      # near white
            continue
        if mx < 18:                    # near black
            continue
        keep.append((r, g, b))
    if len(keep) < 30:
        keep = pixels

    n = len(keep)
    r = sum(p[0] for p in keep) / n
    g = sum(p[1] for p in keep) / n
    b = sum(p[2] for p in keep) / n

    hexcode = "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    family = _family_for_hsv(h * 360, s, v)
    return hexcode, family
