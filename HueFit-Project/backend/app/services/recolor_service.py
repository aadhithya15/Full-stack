"""Deterministic HueFit garment recolouring.

The engine keeps fabric folds and texture while moving the garment toward
an AI-selected target colour. Valid exact-binary mask collections pass through
unchanged. A deliberately conservative, overlap-safe 3x3 closing is reserved
for malformed fallback assets; it is never a replacement for source-mask QA.
"""
from __future__ import annotations

import colorsys
import io

import numpy as np
from PIL import Image, ImageChops, ImageFilter

try:
    _LANCZOS = Image.Resampling.LANCZOS
    _NEAREST = Image.Resampling.NEAREST
except AttributeError:  # Pillow < 9.1 compatibility
    _LANCZOS = Image.LANCZOS
    _NEAREST = Image.NEAREST


def _hex_to_rgb(hexcode: str) -> tuple[int, int, int]:
    value = (hexcode or "").lstrip("#")
    if len(value) != 6:
        raise ValueError(f"bad hex colour: {hexcode!r}")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"bad hex colour: {hexcode!r}") from exc


def repair_mask(mask: Image.Image, size: tuple[int, int] | None = None) -> Image.Image:
    """Binarize a mask and close only tiny holes/gaps.

    MaxFilter followed by MinFilter is a 3x3 morphological close. OR-ing the
    result with the source guarantees that valid source-mask pixels are never
    removed. Large tears, background leaks, skin leaks, and wrong garments
    still have to fail visual QA at the source.
    """
    binary = mask.convert("L")
    if size is not None and binary.size != size:
        binary = binary.resize(size, _NEAREST)
    binary = binary.point(lambda value: 255 if value >= 128 else 0, mode="L")
    closed = binary.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    return ImageChops.lighter(binary, closed)


def repair_mask_set(
    masks: list[Image.Image],
    size: tuple[int, int],
) -> list[Image.Image]:
    """Preserve valid mask sets exactly; repair only malformed fallbacks.

    A same-size, exact-binary, non-overlapping collection is authoritative and
    passes through pixel-for-pixel. If a collection is malformed (wrong size,
    antialiasing, or overlap), it is binarized, first ownership wins existing
    overlap, and only uncontested 3x3-closing additions are admitted. This keeps
    a bad optional asset available without weakening QA for approved assets.
    """
    if not masks:
        return []

    exact_source = True
    raw_arrays: list[np.ndarray] = []
    for mask in masks:
        original = mask.convert("L")
        original_array = np.asarray(original, dtype=np.uint8)
        exact_source &= original.size == size and bool(
            np.all((original_array == 0) | (original_array == 255))
        )
        if original.size != size:
            original = original.resize(size, _NEAREST)
        raw = original.point(lambda value: 255 if value >= 128 else 0, mode="L")
        raw_arrays.append(np.asarray(raw, dtype=np.uint8) >= 128)

    ownership = np.zeros(size[::-1], dtype=np.uint8)
    for raw_array in raw_arrays:
        ownership += raw_array.astype(np.uint8)
    if exact_source and not bool((ownership > 1).any()):
        return [
            Image.fromarray((raw_array * 255).astype(np.uint8), "L")
            for raw_array in raw_arrays
        ]

    # Resolve malformed existing overlap deterministically before considering
    # any gap additions. Earlier semantic masks retain ownership.
    claimed = np.zeros(size[::-1], dtype=bool)
    owned_arrays: list[np.ndarray] = []
    for raw_array in raw_arrays:
        owned = raw_array & ~claimed
        owned_arrays.append(owned)
        claimed |= owned

    proposed_arrays: list[np.ndarray] = []
    for owned in owned_arrays:
        owned_image = Image.fromarray((owned * 255).astype(np.uint8), "L")
        repaired = repair_mask(owned_image)
        repaired_array = np.asarray(repaired, dtype=np.uint8) >= 128
        proposed_arrays.append(repaired_array & ~owned)

    raw_union = np.logical_or.reduce(owned_arrays)
    proposal_count = np.zeros(raw_union.shape, dtype=np.uint8)
    for proposal in proposed_arrays:
        proposal_count += proposal.astype(np.uint8)

    output: list[Image.Image] = []
    for owned, proposal in zip(owned_arrays, proposed_arrays):
        safe_additions = proposal & ~raw_union & (proposal_count == 1)
        final = owned | safe_additions
        output.append(Image.fromarray((final * 255).astype(np.uint8), "L"))
    return output


def _target_rgb_field(
    hue: float,
    saturation: np.ndarray,
    value: np.ndarray,
) -> np.ndarray:
    """Vectorized HSV-to-RGB for one hue and per-pixel saturation/value."""
    hue6 = (hue % 1.0) * 6.0
    sector = int(hue6) % 6
    fraction = hue6 - int(hue6)

    chroma = value * saturation
    x_value = chroma * (1.0 - abs((hue6 % 2.0) - 1.0))
    zero = np.zeros_like(chroma)
    combinations = {
        0: (chroma, x_value, zero),
        1: (x_value, chroma, zero),
        2: (zero, chroma, x_value),
        3: (zero, x_value, chroma),
        4: (x_value, zero, chroma),
        5: (chroma, zero, x_value),
    }
    red, green, blue = combinations[sector]
    match = value - chroma
    return np.stack((red + match, green + match, blue + match), axis=2)


def recolor_garment(
    template: Image.Image,
    mask: Image.Image,
    target_hex: str,
    strength: float = 1.0,
    *,
    repair: bool = True,
) -> Image.Image:
    """Recolour one masked garment while preserving shading and texture."""
    target_red, target_green, target_blue = _hex_to_rgb(target_hex)
    target_hue, target_saturation, target_value = colorsys.rgb_to_hsv(
        target_red / 255.0,
        target_green / 255.0,
        target_blue / 255.0,
    )

    base = template.convert("RGB")
    if repair:
        clean_mask = repair_mask(mask, base.size)
    else:
        clean_mask = mask.convert("L")
        if clean_mask.size != base.size:
            clean_mask = clean_mask.resize(base.size, _NEAREST)
        clean_mask = clean_mask.point(
            lambda value: 255 if value >= 128 else 0,
            mode="L",
        )
    alpha_raw = np.asarray(clean_mask, dtype=np.float32) / 255.0
    selected = alpha_raw >= 0.5
    if not selected.any():
        return base

    source = np.asarray(base, dtype=np.float32) / 255.0
    source_value = source.max(axis=2)
    garment_values = source_value[selected]

    # Percentile tone mapping works even when the original garment is very
    # dark. It maps source folds into a target-centred brightness range rather
    # than multiplying by a gain that can never lift near-black cloth enough.
    low = float(np.percentile(garment_values, 4.0))
    high = float(np.percentile(garment_values, 96.0))
    if high - low < 0.04:
        low = max(0.0, float(garment_values.mean()) - 0.12)
        high = min(1.0, float(garment_values.mean()) + 0.12)
    shade = np.clip((source_value - low) / max(high - low, 0.04), 0.0, 1.0)

    # Anchor the median garment pixel exactly at the requested target value.
    # Limited shadow/highlight room keeps the overall cloth visibly close to
    # the requested colour instead of turning dark emerald into neon green.
    shade_center = float(np.median(shade[selected]))
    shade_center = min(0.90, max(0.10, shade_center))
    shadow_room = max(0.0, min(target_value - 0.025, 0.28 + 0.15 * target_value))
    highlight_room = max(
        0.0, min(1.0 - target_value, 0.22 + 0.10 * (1.0 - target_value))
    )
    mapped_value = np.where(
        shade < shade_center,
        target_value
        - (shade_center - shade) / max(shade_center, 0.10) * shadow_room,
        target_value
        + (shade - shade_center) / max(1.0 - shade_center, 0.10) * highlight_room,
    )
    mapped_value = np.clip(mapped_value, 0.025, 1.0)

    # Real cloth loses some saturation in bright folds and deep shadows.
    # Mid-tones remain closest to the requested target colour.
    midtone = 1.0 - np.minimum(np.abs(shade - 0.52) / 0.52, 1.0)
    saturation_scale = 0.70 + 0.30 * midtone
    mapped_saturation = np.clip(target_saturation * saturation_scale, 0.0, 1.0)

    recoloured = _target_rgb_field(target_hue, mapped_saturation, mapped_value)
    output = source.copy()
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength >= 1.0:
        output[selected] = recoloured[selected]
    elif strength > 0.0:
        output[selected] = (
            recoloured[selected] * strength + source[selected] * (1.0 - strength)
        )

    changed = Image.fromarray(np.clip(output * 255.0, 0, 255).astype(np.uint8), "RGB")
    soft_mask = clean_mask.filter(ImageFilter.GaussianBlur(0.8))
    return Image.composite(changed, base, soft_mask)


def recolor_garments(
    template: Image.Image,
    masks: list[Image.Image],
    target_hexes: list[str],
) -> Image.Image:
    """Recolour every available mask, cycling AI colours when necessary."""
    if not masks or not target_hexes:
        return template.convert("RGB")
    result = template.convert("RGB")
    clean_masks = repair_mask_set(masks, result.size)
    for index, mask in enumerate(clean_masks):
        colour = target_hexes[index % len(target_hexes)]
        result = recolor_garment(result, mask, colour, repair=False)
    return result


def recolor_to_bytes(
    template: Image.Image,
    mask: Image.Image,
    target_hex: str,
    quality: int = 88,
) -> bytes:
    """Backward-compatible one-mask JPEG helper."""
    result = recolor_garment(template, mask, target_hex)
    buffer = io.BytesIO()
    result.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def recolor_many_to_bytes(
    template: Image.Image,
    masks: list[Image.Image],
    target_hexes: list[str],
    quality: int = 88,
) -> bytes:
    """Recolour all masks and return JPEG bytes."""
    result = recolor_garments(template, masks, target_hexes)
    buffer = io.BytesIO()
    result.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()
