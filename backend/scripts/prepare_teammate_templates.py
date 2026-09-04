"""Prepare the latest HueFit template manifest for upload.

Expected source layout (repository main):
    template/pieces.json
    template/base/*.jpg
    template/universal-masking/*.png

The source manifest has one exact mask per visible garment piece. HueFit receives
at most three AI colours, normally two, so this script merges related pieces
into explicit semantic colour groups. It also derives six natural skin-depth
variants from each base master while guaranteeing that no garment pixel moves.

No broad garment-mask reconstruction happens here. Source-mask defects fail the
preparation gate instead of being hidden. Runtime retains only a conservative,
overlap-safe 3x3 pinhole defense.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

try:
    from scipy import ndimage
except ImportError as exc:  # pragma: no cover - environment error path
    raise SystemExit(
        "Template preparation needs scipy. Install it once with: pip install scipy"
    ) from exc

NATIVE_TONES = (
    "fair",
    "light-warm",
    "light-tan",
    "medium-brown",
    "deep",
    "ebony",
)
# PIL HSV values use a 0-255 scale. These targets retain natural warm chroma
# while stepping brightness monotonically from fair to ebony.
TONE_LADDER = {
    "fair": (220.0, 70.0),
    "light-warm": (205.0, 85.0),
    "light-tan": (185.0, 100.0),
    "medium-brown": (165.0, 112.0),
    "deep": (140.0, 118.0),
    "ebony": (115.0, 115.0),
}
MAX_HEIGHT = 1376
EXPECTED_IDS = tuple(
    [f"M{index}" for index in range(1, 16)]
    + [f"W{index}" for index in range(1, 18)]
)

try:
    LANCZOS = Image.Resampling.LANCZOS
    NEAREST = Image.Resampling.NEAREST
except AttributeError:  # Pillow < 9.1 compatibility
    LANCZOS = Image.LANCZOS
    NEAREST = Image.NEAREST

# A group value selects AI colour 1 or 2. None means the manifest intentionally
# marks a fully occluded z:0 piece. The table is explicit because grouping is a
# fashion-semantic decision, not a filename or RGB-code coincidence.
COLOUR_GROUPS: dict[str, tuple[int | None, ...]] = {
    "M1": (0, 1),
    "M2": (0, 1, 0),
    "M3": (0, 1, None),
    "M4": (0, 1, 0, None),
    "M5": (0, 1, None),
    "M6": (0, 1),
    "M7": (0, 1),
    "M8": (0, 1, 0),
    "M9": (0, 1, None),
    "M10": (0, 1, 0),
    "M11": (0, 1, None, 1),
    "M12": (0, 1),
    "M13": (0, 1),
    "M14": (0, 1),
    "M15": (0, 1, 0),
    "W1": (0, 1),
    "W2": (0, 1, 0),
    "W3": (0, 1),
    "W4": (0, 1, 0),
    "W5": (0, 1),
    "W6": (0, 1, 0),
    "W7": (0, 1),
    "W8": (0,),
    "W9": (0,),
    "W10": (0,),
    "W11": (0,),
    "W12": (0, 1),
    "W13": (0, 1, 0),
    "W14": (0, 1),
    # The manifest says this self-fabric belt must match the kaftan.
    "W15": (0, 0),
    "W16": (0, 1),
    "W17": (0,),
}

DRESS_OVERRIDES = {
    "M8": "nehru-jacket",
    "M11": "pathani-suit",
    "W8": "gown",
    "W17": "gown",
}

# culture, semicolon-delimited style tags
META: dict[str, tuple[str, str]] = {
    "M1": ("western", "formal"),
    "M2": ("western", "formal;smart-casual"),
    "M3": ("western", "formal"),
    "M4": ("western", "formal"),
    "M5": ("western", "formal;party"),
    "M6": ("tamil", "traditional"),
    "M7": ("tamil", "traditional;festive"),
    "M8": ("fusion", "formal;festive"),
    "M9": ("tamil", "traditional;festive"),
    "M10": ("fusion", "formal;festive"),
    "M11": ("tamil", "traditional"),
    "M12": ("western", "casual"),
    "M13": ("western", "casual"),
    "M14": ("western", "formal"),
    "M15": ("fusion", "formal;festive"),
    "W1": ("tamil", "traditional;festive"),
    "W2": ("tamil", "traditional;festive"),
    "W3": ("tamil", "traditional;festive"),
    "W4": ("tamil", "traditional"),
    "W5": ("tamil", "casual;traditional"),
    "W6": ("tamil", "traditional;festive"),
    "W7": ("tamil", "traditional;festive"),
    "W8": ("western", "party;formal"),
    "W9": ("western", "casual;party"),
    "W10": ("western", "casual;party"),
    "W11": ("western", "party;casual"),
    "W12": ("western", "casual"),
    "W13": ("western", "formal"),
    "W14": ("western", "casual"),
    "W15": ("fusion", "casual;festive"),
    "W16": ("western", "casual"),
    "W17": ("western", "party;formal"),
}

CSV_FIELDS = (
    "template_code",
    "dress_type",
    "gender",
    "culture",
    "style_tags",
    "base_hue_family",
    "image_file",
    "mask_file",
    "mask2_file",
    "mask3_file",
    "tone_variants",
    "notes",
)


def _find_root(source: Path) -> Path:
    for candidate in (source, source / "template"):
        if (
            (candidate / "pieces.json").is_file()
            and (candidate / "base").is_dir()
            and (candidate / "universal-masking").is_dir()
        ):
            return candidate
    raise ValueError(
        "Could not find template/pieces.json + base + universal-masking under "
        + str(source)
    )


def _load_manifest(root: Path) -> list[dict[str, Any]]:
    value = json.loads((root / "pieces.json").read_text(encoding="utf-8"))
    outfits = value.get("outfits") if isinstance(value, dict) else None
    if not isinstance(outfits, list):
        raise ValueError("pieces.json must contain an outfits list")
    ids = tuple(str(outfit.get("id")) for outfit in outfits)
    if ids != EXPECTED_IDS:
        raise ValueError(
            "unexpected outfit ids/order: expected "
            + ",".join(EXPECTED_IDS)
            + " but got "
            + ",".join(ids)
        )
    return outfits


def _binary_array(path: Path, size: tuple[int, int]) -> np.ndarray:
    with Image.open(path) as opened:
        mask = opened.convert("L")
        if mask.size != size:
            raise ValueError(
                f"mask size mismatch: {path} is {mask.size}, base is {size}"
            )
        array = np.asarray(mask, dtype=np.uint8)
    if np.any((array != 0) & (array != 255)):
        raise ValueError(f"mask is not exact binary: {path}")
    return array >= 128


def _correct_known_source_defect(
    outfit_id: str,
    piece_name: str,
    rgb: np.ndarray,
    mask: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any] | None]:
    """Apply a reviewed, fail-closed correction for a visible source defect."""
    if outfit_id != "M4" or piece_name != "waistcoat":
        return mask, None

    # The shipped M4 waistcoat mask incorrectly owns the dark necktie even
    # though pieces.json and README classify the tie as uncoded. Find that one
    # dark central component, fill its tiny highlight holes, and add a one-pixel
    # safety rim. Bounds and area checks make this fail if the master changes.
    height, width = mask.shape
    yy, xx = np.mgrid[0:height, 0:width]
    red = rgb[..., 0].astype(np.int16)
    blue = rgb[..., 2].astype(np.int16)
    search = (
        mask
        & (xx >= 330)
        & (xx <= 425)
        & (yy >= 175)
        & (yy <= 350)
        & ((blue - red) < 50)
    )
    labels, count = ndimage.label(search, np.ones((3, 3)))
    if count == 0:
        raise ValueError("M4 waistcoat correction could not find the necktie")
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    tie = labels == int(np.argmax(sizes[1:]) + 1)
    tie = ndimage.binary_fill_holes(tie)
    tie = ndimage.binary_dilation(tie, np.ones((3, 3))) & mask
    removed = int(tie.sum())
    if not 4000 <= removed <= 4400:
        raise ValueError(
            f"M4 waistcoat necktie correction expected 4000-4400 pixels, got {removed}"
        )
    corrected = mask & ~tie
    return corrected, {
        "outfit": outfit_id,
        "piece": piece_name,
        "removed_pixels": removed,
        "reason": "dark necktie was incorrectly owned by the waistcoat mask",
    }


def _validate_and_load(
    root: Path,
    outfits: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    loaded: dict[str, dict[str, Any]] = {}
    corrections: list[dict[str, Any]] = []
    for outfit in outfits:
        outfit_id = str(outfit["id"])
        pieces = outfit.get("pieces")
        groups = COLOUR_GROUPS[outfit_id]
        if not isinstance(pieces, list) or len(pieces) != len(groups):
            raise ValueError(
                f"{outfit_id}: manifest piece count does not match semantic groups"
            )
        image_path = root / str(outfit.get("image") or "")
        if not image_path.is_file():
            raise ValueError(f"{outfit_id}: image not found: {image_path}")
        with Image.open(image_path) as opened:
            opened.load()
            if opened.mode not in ("RGB", "RGBA"):
                raise ValueError(f"{outfit_id}: base image is not RGB/RGBA")
            size = opened.size
            rgb = np.asarray(opened.convert("RGB"), dtype=np.uint8)
        if size != (768, 1376):
            raise ValueError(f"{outfit_id}: expected 768x1376, got {size}")

        piece_arrays: list[np.ndarray] = []
        ownership = np.zeros(size[::-1], dtype=np.uint8)
        for index, (piece, group) in enumerate(zip(pieces, groups)):
            path = root / str(piece.get("mask") or "")
            if not path.is_file():
                raise ValueError(f"{outfit_id}: mask not found: {path}")
            array = _binary_array(path, size)
            array, correction = _correct_known_source_defect(
                outfit_id,
                str(piece.get("piece") or ""),
                rgb,
                array,
            )
            if correction:
                correction["source_mask"] = str(piece.get("mask") or "")
                corrections.append(correction)
            z = int(piece.get("z", -1))
            if group is None:
                if z != 0 or array.any():
                    raise ValueError(
                        f"{outfit_id} piece {index}: semantic None requires empty z:0 mask"
                    )
            else:
                if z != 1 or not array.any():
                    raise ValueError(
                        f"{outfit_id} piece {index}: grouped piece requires non-empty z:1 mask"
                    )
            ownership += array.astype(np.uint8)
            piece_arrays.append(array)
        overlap = int((ownership > 1).sum())
        if overlap:
            raise ValueError(f"{outfit_id}: source masks overlap by {overlap} pixels")
        loaded[outfit_id] = {
            "image_path": image_path,
            "size": size,
            "piece_arrays": piece_arrays,
        }
    return loaded, corrections


def _generic_skin(rgb: np.ndarray) -> np.ndarray:
    image = Image.fromarray(rgb.astype(np.uint8), "RGB")
    ycc = np.asarray(image.convert("YCbCr"), dtype=np.float32)
    hsv = np.asarray(image.convert("HSV"), dtype=np.float32)
    red, green, blue = [rgb[..., index].astype(np.int16) for index in range(3)]
    y, cb, cr = ycc[..., 0], ycc[..., 1], ycc[..., 2]
    saturation, value = hsv[..., 1], hsv[..., 2]
    return (
        (cr >= 132)
        & (cr <= 181)
        & (cb >= 72)
        & (cb <= 137)
        & (red > green + 1)
        & (red > blue + 4)
        & (value > 48)
        & (value < 248)
        & (saturation > 18)
        & (saturation < 190)
        & (y > 38)
        & (y < 238)
    )


def _background_residual(rgb: np.ndarray) -> np.ndarray:
    """Return distance from a smooth model fitted to empty studio margins."""
    rgb_float = np.asarray(rgb, dtype=np.float32)
    height, width = rgb_float.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    xn = (xx - width / 2.0) / max(1.0, float(width))
    yn = (yy - height / 2.0) / max(1.0, float(height))
    design = np.stack(
        (
            np.ones_like(xn),
            xn,
            yn,
            xn * xn,
            yn * yn,
            xn * yn,
            xn**3,
            yn**3,
            xn * xn * yn,
            xn * yn * yn,
        ),
        axis=2,
    )
    margin = (xx < width * 0.16) | (xx > width * 0.84) | (yy < height * 0.025)
    sample = margin & (xx % 7 == 0) & (yy % 7 == 0)
    matrix = design[sample]
    predicted = np.empty_like(rgb_float)
    for channel in range(3):
        coefficients = np.linalg.lstsq(
            matrix,
            rgb_float[..., channel][sample],
            rcond=None,
        )[0]
        predicted[..., channel] = design @ coefficients
    return np.sqrt(((rgb_float - predicted) ** 2).sum(axis=2))


def _skin_mask(rgb: np.ndarray, garment_mask: np.ndarray) -> np.ndarray:
    """Find face, neck, arms, hands, and exposed midriff without backdrop."""
    rgb = np.asarray(rgb, dtype=np.uint8)
    garment = np.asarray(garment_mask, dtype=bool)
    height, width = garment.shape
    ys, xs = np.nonzero(garment)
    if not len(ys):
        raise ValueError("empty garment union")
    gx0, gx1 = int(xs.min()), int(xs.max())
    gy0 = int(ys.min())
    centre_x = int(np.median(xs))

    generic = _generic_skin(rgb) & (_background_residual(rgb) >= 42.0)
    cloth_guard = ndimage.binary_dilation(garment, np.ones((5, 5)))
    generic &= ~cloth_guard

    head_half = max(42, min(105, int((gx1 - gx0) * 0.19)))
    face_region = np.zeros((height, width), dtype=bool)
    face_region[
        max(0, gy0 - int(height * 0.19)) : min(height, gy0 + int(height * 0.035)),
        max(0, centre_x - head_half) : min(width, centre_x + head_half),
    ] = True
    seed_candidates = generic & face_region
    labels, count = ndimage.label(seed_candidates, np.ones((3, 3)))
    if count == 0:
        raise ValueError("face skin seed not found")
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    valid = [index for index in range(1, count + 1) if sizes[index] >= 80]
    if not valid:
        raise ValueError("face skin seed too small")
    face_seed = labels == max(valid, key=lambda index: sizes[index])

    ycc = np.asarray(Image.fromarray(rgb, "RGB").convert("YCbCr"), dtype=np.float32)
    cb0 = float(np.median(ycc[..., 1][face_seed]))
    cr0 = float(np.median(ycc[..., 2][face_seed]))
    chroma_distance = np.sqrt(
        ((ycc[..., 1] - cb0) / 18.0) ** 2
        + ((ycc[..., 2] - cr0) / 18.0) ** 2
    )
    candidate = generic & (chroma_distance <= 2.0)
    candidate = ndimage.binary_opening(candidate, np.ones((2, 2)))

    distance_to_cloth = ndimage.distance_transform_edt(~garment)
    body_zone = (
        (distance_to_cloth <= 42)
        & (np.arange(height)[:, None] <= int(height * 0.86))
        & (np.arange(width)[None, :] >= gx0 - 55)
        & (np.arange(width)[None, :] <= gx1 + 55)
    )
    labels, count = ndimage.label(candidate, np.ones((3, 3)))
    keep = np.zeros((height, width), dtype=bool)
    for index in range(1, count + 1):
        component = labels == index
        area = int(component.sum())
        if area < 25:
            continue
        cy, cx = np.nonzero(component)
        touches_frame = (
            cy.min() == 0
            or cy.max() == height - 1
            or cx.min() == 0
            or cx.max() == width - 1
        )
        if touches_frame or area > int(height * width * 0.08):
            continue
        is_face = bool((component & face_region).sum() >= 20)
        near_count = int((component & body_zone).sum())
        is_body_skin = near_count >= max(20, int(area * 0.80))
        if is_face or is_body_skin:
            keep |= component

    keep = ndimage.binary_closing(keep, np.ones((3, 3)))
    keep &= ~cloth_guard
    if int(keep.sum()) < 500:
        raise ValueError(f"skin mask too small: {int(keep.sum())} pixels")
    return keep


def _apply_tone(
    rgb: np.ndarray,
    skin: np.ndarray,
    garment_mask: np.ndarray,
    target_value: float,
    target_saturation: float,
) -> np.ndarray:
    """Retone skin in true HSV while preserving hue, texture, and garments."""
    hsv = np.asarray(Image.fromarray(rgb, "RGB").convert("HSV"), dtype=np.float32).copy()
    current_value = float(hsv[..., 2][skin].mean())
    current_saturation = float(hsv[..., 1][skin].mean())
    adjusted = hsv.copy()
    adjusted[..., 2] = np.clip(
        adjusted[..., 2] + target_value - current_value,
        0,
        255,
    )
    adjusted[..., 1] = np.clip(
        adjusted[..., 1] + target_saturation - current_saturation,
        0,
        255,
    )
    # adjusted contains HSV bytes. Declaring that mode before RGB conversion is
    # essential; interpreting these bytes as RGB made the repository output blue.
    shifted = np.asarray(
        Image.fromarray(adjusted.astype(np.uint8), mode="HSV").convert("RGB"),
        dtype=np.float32,
    )
    alpha = np.asarray(
        Image.fromarray((skin * 255).astype(np.uint8), "L").filter(
            ImageFilter.GaussianBlur(0.8)
        ),
        dtype=np.float32,
    ) / 255.0
    alpha[garment_mask] = 0.0
    output = shifted * alpha[..., None] + rgb.astype(np.float32) * (1.0 - alpha[..., None])
    output = np.clip(output, 0, 255).astype(np.uint8)

    moved = np.abs(output.astype(np.int16) - rgb.astype(np.int16)).max(axis=2) > 0
    garment_movement = int((moved & garment_mask).sum())
    if garment_movement:
        raise RuntimeError(f"skin tone moved {garment_movement} garment pixels")
    far_from_skin = ~ndimage.binary_dilation(skin, np.ones((7, 7)))
    backdrop_movement = int((moved & far_from_skin).sum())
    if backdrop_movement:
        raise RuntimeError(
            f"skin tone moved {backdrop_movement} pixels away from detected skin"
        )
    return output


def _target_size(size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    if height <= MAX_HEIGHT:
        return size
    ratio = MAX_HEIGHT / height
    return max(1, round(width * ratio)), MAX_HEIGHT


def _save_base(source: Path, destination: Path, size: tuple[int, int]) -> np.ndarray:
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        if image.size != size:
            image = image.resize(size, LANCZOS)
            image.save(destination, "JPEG", quality=95, optimize=True, subsampling=0)
        else:
            # Preserve the authoritative master bytes when no resize is needed.
            shutil.copyfile(source, destination)
        return np.asarray(image, dtype=np.uint8)


def _dress_type(outfit: dict[str, Any]) -> str:
    outfit_id = str(outfit["id"])
    return DRESS_OVERRIDES.get(outfit_id, str(outfit["slug"]))


def _template_code(outfit: dict[str, Any]) -> str:
    outfit_id = str(outfit["id"])
    gender_letter = "m" if outfit_id.startswith("M") else "f"
    serial = "02" if outfit_id == "W17" else "01"
    return f"{_dress_type(outfit)}_{gender_letter}_{serial}"


def prepare(source_folder: Path, output_folder: Path) -> int:
    root = _find_root(source_folder)
    outfits = _load_manifest(root)
    loaded, corrections = _validate_and_load(root, outfits)

    if output_folder.exists():
        shutil.rmtree(output_folder)
    output_folder.mkdir(parents=True)

    rows: list[dict[str, str]] = []
    skin_report: list[dict[str, Any]] = []
    print("input layout: pieces-manifest-v2")
    print("source:", root)
    print("output:", output_folder)

    for outfit in outfits:
        outfit_id = str(outfit["id"])
        code = _template_code(outfit)
        data = loaded[outfit_id]
        source_size = data["size"]
        size = _target_size(source_size)
        image_name = f"{code}.jpg"
        rgb = _save_base(data["image_path"], output_folder / image_name, size)

        piece_arrays = data["piece_arrays"]
        if size != source_size:
            resized: list[np.ndarray] = []
            for array in piece_arrays:
                mask = Image.fromarray((array * 255).astype(np.uint8), "L")
                resized.append(np.asarray(mask.resize(size, NEAREST)) >= 128)
            piece_arrays = resized

        group_arrays: list[np.ndarray] = []
        group_names: list[list[str]] = []
        groups = COLOUR_GROUPS[outfit_id]
        for group_index in sorted({group for group in groups if group is not None}):
            combined = np.zeros(size[::-1], dtype=bool)
            names: list[str] = []
            for piece, array, assigned in zip(outfit["pieces"], piece_arrays, groups):
                if assigned == group_index:
                    combined |= array
                    names.append(str(piece["piece"]))
            if not combined.any():
                raise ValueError(f"{outfit_id}: semantic group {group_index} is empty")
            group_arrays.append(combined)
            group_names.append(names)

        ownership = np.zeros(size[::-1], dtype=np.uint8)
        for array in group_arrays:
            ownership += array.astype(np.uint8)
        if int((ownership > 1).sum()):
            raise ValueError(f"{outfit_id}: merged semantic masks overlap")

        mask_names: list[str] = []
        coverages: list[float] = []
        for index, array in enumerate(group_arrays, start=1):
            suffix = "_mask.png" if index == 1 else f"_mask{index}.png"
            name = code + suffix
            Image.fromarray((array * 255).astype(np.uint8), "L").save(
                output_folder / name,
                "PNG",
                optimize=True,
            )
            mask_names.append(name)
            coverages.append(float(array.mean()))

        garment_union = np.logical_or.reduce(group_arrays)
        skin = _skin_mask(rgb, garment_union)
        variants: dict[str, str] = {}
        tone_means: list[float] = []
        for tone in NATIVE_TONES:
            target_value, target_saturation = TONE_LADDER[tone]
            variant = _apply_tone(
                rgb,
                skin,
                garment_union,
                target_value,
                target_saturation,
            )
            variant_name = f"{code}__{tone}.jpg"
            Image.fromarray(variant, "RGB").save(
                output_folder / variant_name,
                "JPEG",
                quality=95,
                optimize=True,
                subsampling=0,
            )
            variants[tone] = variant_name
            ycc = np.asarray(Image.fromarray(variant, "RGB").convert("YCbCr"))
            tone_means.append(float(ycc[..., 0][skin].mean()))
        if any(
            first <= second
            for first, second in zip(tone_means, tone_means[1:])
        ):
            raise RuntimeError(f"{outfit_id}: complexion ladder is not strictly darker")

        gender = "male" if outfit_id.startswith("M") else "female"
        culture, tags = META[outfit_id]
        padded_masks = mask_names + [""] * (3 - len(mask_names))
        groups_text = " | ".join(
            f"colour {index + 1}: {','.join(names)}"
            for index, names in enumerate(group_names)
        )
        coverage_text = ", ".join(f"{value:.1%}" for value in coverages)
        correction_text = ""
        if any(item["outfit"] == outfit_id for item in corrections):
            correction_text = "; reviewed correction: M4 necktie excluded"
        rows.append(
            {
                "template_code": code,
                "dress_type": _dress_type(outfit),
                "gender": gender,
                "culture": culture,
                "style_tags": tags,
                "base_hue_family": "",
                "image_file": image_name,
                "mask_file": padded_masks[0],
                "mask2_file": padded_masks[1],
                "mask3_file": padded_masks[2],
                "tone_variants": json.dumps(
                    variants,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "notes": (
                    f"latest-main {outfit_id}; {groups_text}; coverage: {coverage_text}; "
                    f"native tones: {','.join(NATIVE_TONES)}{correction_text}"
                ),
            }
        )
        skin_report.append(
            {
                "id": outfit_id,
                "template_code": code,
                "skin_pixels": int(skin.sum()),
                "skin_percent": round(float(skin.mean() * 100), 3),
                "garment_movement_max": 0,
                "tone_skin_luma": {
                    tone: round(value, 3)
                    for tone, value in zip(NATIVE_TONES, tone_means)
                },
            }
        )
        print(
            f"  {outfit_id:3} {code:30} masks={len(mask_names)} tones=6 "
            f"skin={skin.mean():.2%} size={size[0]}x{size[1]}"
        )

    csv_path = output_folder / "templates.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (output_folder / "skin-tone-report.json").write_text(
        json.dumps(skin_report, indent=2),
        encoding="utf-8",
    )
    (output_folder / "mask-corrections.json").write_text(
        json.dumps(corrections, indent=2),
        encoding="utf-8",
    )

    print("-" * 72)
    print(f"prepared {len(rows)} templates, {sum(1 for _ in output_folder.glob('*_mask*.png'))} masks")
    print(f"generated {len(rows) * len(NATIVE_TONES)} tone variants")
    print("source mask overlap: 0 pixels")
    print(f"reviewed source-mask corrections: {len(corrections)}")
    for correction in corrections:
        print(
            f"  {correction['outfit']} {correction['piece']}: "
            f"removed {correction['removed_pixels']} necktie pixels"
        )
    print("tone garment movement: 0 pixels")
    print("CSV:", csv_path)
    print("Next: run upload_templates.py --dry-run, then visually QA before upload.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Full-stack repository root or template folder")
    parser.add_argument("--out", required=True, help="generated upload folder")
    args = parser.parse_args()
    try:
        return prepare(Path(args.source).resolve(), Path(args.out).resolve())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
