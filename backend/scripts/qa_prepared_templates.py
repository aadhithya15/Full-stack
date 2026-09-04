"""Create visual and numeric QA evidence for a prepared template folder.

Run only after prepare_teammate_templates.py. This script renders all 32 looks
with deliberately contrasting colours, makes four zoomed boundary sheets, and
compares all six native complexions on representative faces. It also fails if
masks overlap, valid masks are changed by runtime, or recolouring moves pixels
outside an authoritative mask.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.recolor_service import recolor_garments, repair_mask_set

TONES = ("fair", "light-warm", "light-tan", "medium-brown", "deep", "ebony")
QA_COLOURS = ("#173F8A", "#C8871A")
FONT = ImageFont.load_default()


def _fit(
    image: Image.Image,
    size: tuple[int, int],
    background: tuple[int, int, int] = (245, 242, 238),
) -> Image.Image:
    result = Image.new("RGB", size, background)
    copy = image.convert("RGB")
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    result.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return result


def _mask_names(row: dict[str, str]) -> list[str]:
    return [
        row[key].strip()
        for key in ("mask_file", "mask2_file", "mask3_file")
        if (row.get(key) or "").strip()
    ]


def _tone_files(row: dict[str, str]) -> dict[str, str]:
    value = json.loads(row.get("tone_variants") or "{}")
    if not isinstance(value, dict) or set(value) != set(TONES):
        raise ValueError(
            f"{row.get('template_code')}: expected exactly six native tone files"
        )
    return {str(key): str(name) for key, name in value.items()}


def _overview(
    rendered: list[tuple[str, Image.Image]],
    destination: Path,
) -> None:
    cell_width, cell_height, header = 240, 430, 24
    columns = 8
    rows = (len(rendered) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * (cell_height + header)),
        (22, 22, 22),
    )
    draw = ImageDraw.Draw(sheet)
    for index, (code, image) in enumerate(rendered):
        row_index, column = divmod(index, columns)
        x = column * cell_width
        y = row_index * (cell_height + header)
        sheet.paste(
            image.resize((cell_width, cell_height), Image.Resampling.LANCZOS),
            (x, y + header),
        )
        draw.text((x + 3, y + 6), code, fill="white", font=FONT)
    sheet.save(destination, "JPEG", quality=94, subsampling=0)


def _details(
    rendered: list[tuple[str, Image.Image]],
    output: Path,
) -> None:
    for batch in range(4):
        subset = rendered[batch * 8 : (batch + 1) * 8]
        panel_width, row_height = 1200, 365
        detail = Image.new("RGB", (panel_width, row_height * len(subset)), "white")
        draw = ImageDraw.Draw(detail)
        for row_index, (code, image) in enumerate(subset):
            y = row_index * row_height
            draw.rectangle((0, y, panel_width, y + 28), fill=(20, 20, 20))
            draw.text(
                (7, y + 8),
                f"{code} | full, face/neck, torso/hands, lower boundary",
                fill="white",
                font=FONT,
            )
            detail.paste(_fit(image, (190, 325), (255, 255, 255)), (5, y + 34))
            width, height = image.size
            crops = (
                image.crop(
                    (
                        int(width * 0.20),
                        int(height * 0.01),
                        int(width * 0.80),
                        int(height * 0.34),
                    )
                ),
                image.crop(
                    (
                        int(width * 0.06),
                        int(height * 0.20),
                        int(width * 0.94),
                        int(height * 0.66),
                    )
                ),
                image.crop(
                    (
                        int(width * 0.10),
                        int(height * 0.54),
                        int(width * 0.90),
                        int(height * 0.99),
                    )
                ),
            )
            for crop, x, box_width in zip(
                crops,
                (205, 530, 865),
                (315, 325, 325),
            ):
                detail.paste(
                    _fit(crop, (box_width, 325), (255, 255, 255)),
                    (x, y + 34),
                )
        detail.save(
            output / f"final-detail-{batch + 1}.jpg",
            "JPEG",
            quality=95,
            subsampling=0,
        )


def _tone_detail(
    rows: list[dict[str, str]],
    prepared: Path,
    output: Path,
) -> None:
    preferred = (
        "three-piece-suit_m_01",
        "nehru-jacket_m_01",
        "casual-coord_m_01",
        "saree_f_01",
        "lehenga-choli_f_01",
        "sharara_f_01",
        "midi-dress_f_01",
        "gown_f_02",
    )
    by_code = {row["template_code"]: row for row in rows}
    selected = [by_code[code] for code in preferred if code in by_code]
    if len(selected) < 8:
        selected = rows[: min(8, len(rows))]

    proof = Image.new(
        "RGB",
        (len(TONES) * 300, len(selected) * 350),
        (235, 232, 228),
    )
    for row_index, row in enumerate(selected):
        variants = _tone_files(row)
        for column, tone in enumerate(TONES):
            with Image.open(prepared / variants[tone]) as opened:
                image = opened.convert("RGB")
            width, height = image.size
            face = image.crop(
                (
                    int(width * 0.25),
                    int(height * 0.005),
                    int(width * 0.75),
                    int(height * 0.34),
                )
            )
            tile = Image.new("RGB", (300, 350), (245, 242, 238))
            tile.paste(_fit(image, (95, 315)), (2, 28))
            tile.paste(_fit(face, (200, 315)), (98, 28))
            tile_draw = ImageDraw.Draw(tile)
            tile_draw.rectangle((0, 0, 300, 27), fill=(18, 18, 18))
            tile_draw.text(
                (4, 8),
                f"{row['template_code']} | {tone}",
                fill="white",
                font=FONT,
            )
            proof.paste(tile, (column * 300, row_index * 350))
    proof.save(output / "tone-six-detail.jpg", "JPEG", quality=96, subsampling=0)


def qa(prepared: Path, output: Path) -> int:
    csv_path = prepared / "templates.csv"
    if not csv_path.is_file():
        raise ValueError(f"templates.csv not found in {prepared}")
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 32:
        raise ValueError(f"expected 32 prepared templates, got {len(rows)}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    report: list[dict[str, object]] = []
    rendered: list[tuple[str, Image.Image]] = []
    for row in rows:
        code = row["template_code"]
        with Image.open(prepared / row["image_file"]) as opened:
            base = opened.convert("RGB")
        masks = [
            Image.open(prepared / name).convert("L")
            for name in _mask_names(row)
        ]
        raw_arrays = [np.asarray(mask, dtype=np.uint8) >= 128 for mask in masks]
        ownership = np.zeros(base.size[::-1], dtype=np.uint8)
        for array in raw_arrays:
            ownership += array.astype(np.uint8)
        overlap = int((ownership > 1).sum())
        clean = repair_mask_set(masks, base.size)
        exact = all(
            source.tobytes() == result.tobytes()
            for source, result in zip(masks, clean)
        )
        union = np.logical_or.reduce(raw_arrays)

        variants = _tone_files(row)
        with Image.open(prepared / variants["medium-brown"]) as opened:
            medium = opened.convert("RGB")
        result = recolor_garments(medium, masks, list(QA_COLOURS))
        source_array = np.asarray(medium, dtype=np.int16)
        result_array = np.asarray(result, dtype=np.int16)
        moved = np.max(np.abs(result_array - source_array), axis=2) > 0
        outside = int((moved & ~union).sum())
        rendered.append((code, result))
        report.append(
            {
                "template_code": code,
                "masks": len(masks),
                "overlap_pixels": overlap,
                "valid_masks_pass_through_exactly": exact,
                "recolour_changed_outside_mask_pixels": outside,
            }
        )

    summary = {
        "templates": len(report),
        "prepared_masks": sum(int(item["masks"]) for item in report),
        "native_tone_outputs": len(rows) * len(TONES),
        "overlap_pixels_max": max(int(item["overlap_pixels"]) for item in report),
        "all_valid_masks_pass_through_exactly": all(
            bool(item["valid_masks_pass_through_exactly"]) for item in report
        ),
        "recolour_changed_outside_mask_pixels_max": max(
            int(item["recolour_changed_outside_mask_pixels"]) for item in report
        ),
    }
    if (
        summary["overlap_pixels_max"] != 0
        or not summary["all_valid_masks_pass_through_exactly"]
        or summary["recolour_changed_outside_mask_pixels_max"] != 0
    ):
        raise RuntimeError("numeric prepared-template QA failed; see qa-report.json")

    (output / "qa-report.json").write_text(
        json.dumps({"summary": summary, "templates": report}, indent=2),
        encoding="utf-8",
    )
    _overview(rendered, output / "final-all32.jpg")
    _details(rendered, output)
    _tone_detail(rows, prepared, output)
    print(json.dumps(summary, indent=2))
    print("Visual QA files:", output)
    print("Open final-all32.jpg, all four final-detail files, and tone-six-detail.jpg.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prepared", help="folder made by prepare_teammate_templates.py")
    parser.add_argument("--out", required=True, help="QA evidence folder")
    args = parser.parse_args()
    try:
        return qa(Path(args.prepared).resolve(), Path(args.out).resolve())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
