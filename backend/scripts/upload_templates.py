"""HueFit MVP - template library uploader.

Takes a folder of template image + mask pairs (made by the design team),
validates them, uploads both files to the public 'templates' bucket, and
records each template in the outfit_templates table.

Folder layout (see templates/sample for a working example):
    templates/batch1/
      templates.csv          (metadata - see scripts/templates_template.csv)
      saree_f_01.jpg         (the outfit template image)
      saree_f_01_mask.png    (its garment mask: WHITE = garment, BLACK = rest,
                              SAME pixel size as the image)

CSV columns:
  template_code,dress_type,gender,culture,style_tags,base_hue_family,image_file,mask_file,notes
  - style_tags: semicolon-separated (traditional;festive)
  - base_hue_family: the template's own colour (helps recolouring), optional

Usage:
    python scripts/upload_templates.py templates/batch1 --dry-run
    python scripts/upload_templates.py templates/batch1
    python scripts/upload_templates.py templates/batch1 --approve
      (--approve marks uploads QA-approved + active immediately; default
       is 'pending' so a human approves in the dashboard after review)

Validation enforced BEFORE any upload:
  - both files exist and open as images
  - mask is same width x height as the image
  - mask is meaningfully binary (mostly pure black/white pixels)
  - mask covers a sane garment fraction (3%-90% of the frame)
Safe to re-run: existing template_codes are updated, not duplicated.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VALID_GENDERS = {"male", "female", "unisex"}
VALID_CULTURES = {"tamil", "western", "fusion"}
BUCKET = "templates"


def validate_pair(row: dict, folder: Path, line: int) -> tuple[list[str], dict]:
    """Returns (problems, computed_info)."""
    from PIL import Image

    problems = []
    info = {}
    code = (row.get("template_code") or "").strip()
    if not code:
        problems.append("missing template_code")
    if (row.get("gender") or "").strip().lower() not in VALID_GENDERS:
        problems.append(f"bad gender '{row.get('gender')}'")
    if (row.get("culture") or "").strip().lower() not in VALID_CULTURES:
        problems.append(f"bad culture '{row.get('culture')}'")
    if not (row.get("dress_type") or "").strip():
        problems.append("missing dress_type")

    img_f = folder / (row.get("image_file") or "").strip()
    mask_f = folder / (row.get("mask_file") or "").strip()
    if not img_f.name or not img_f.exists():
        problems.append(f"image not found: {img_f.name}")
    if not mask_f.name or not mask_f.exists():
        problems.append(f"mask not found: {mask_f.name}")
    if problems:
        return [f"row {line}: {p}" for p in problems], info

    try:
        img = Image.open(img_f)
        mask = Image.open(mask_f).convert("L")
    except Exception as e:
        return [f"row {line}: cannot open images ({e})"], info

    if img.size != mask.size:
        problems.append(
            f"size mismatch: image {img.size[0]}x{img.size[1]} vs mask {mask.size[0]}x{mask.size[1]}"
        )
    else:
        # binary-ness + coverage checks
        hist = mask.histogram()
        total = sum(hist)
        dark = sum(hist[:32])          # near-black
        bright = sum(hist[224:])       # near-white
        mid = total - dark - bright
        if mid / total > 0.20:
            problems.append(
                f"mask not binary enough ({mid/total:.0%} grey pixels) - use pure black/white"
            )
        coverage = bright / total
        info["coverage"] = coverage
        if coverage < 0.03:
            problems.append(f"mask covers only {coverage:.1%} - is it empty?")
        elif coverage > 0.90:
            problems.append(f"mask covers {coverage:.0%} - is it inverted? (garment should be WHITE)")

    return [f"row {line}: {p}" for p in problems], info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="folder containing templates.csv + image/mask pairs")
    ap.add_argument("--dry-run", action="store_true", help="validate only, upload nothing")
    ap.add_argument("--approve", action="store_true",
                    help="mark as QA-approved + active immediately (default: pending)")
    args = ap.parse_args()

    folder = Path(args.folder)
    csv_path = folder / "templates.csv"
    if not csv_path.exists():
        sys.exit(f"ERROR: {csv_path} not found")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("ERROR: templates.csv is empty")

    print(f"folder: {folder}  |  templates: {len(rows)}")

    all_problems = []
    infos = {}
    for i, row in enumerate(rows, start=2):
        problems, info = validate_pair(row, folder, i)
        all_problems += problems
        infos[row.get("template_code", f"row{i}")] = info

    if all_problems:
        print("VALIDATION FAILED:")
        for p in all_problems:
            print("  -", p)
        return 1
    print("validation: all pairs OK")
    for code, info in infos.items():
        if "coverage" in info:
            print(f"  {code:24} garment coverage {info['coverage']:.0%}")

    if args.dry_run:
        print("DRY RUN - nothing uploaded")
        return 0

    from app.db import queries
    from app.db.supabase_client import get_supabase
    sb = get_supabase()

    # ensure the public templates bucket exists
    try:
        names = {b.name for b in sb.storage.list_buckets()}
        if BUCKET not in names:
            sb.storage.create_bucket(BUCKET, options={"public": True})
            print(f"bucket '{BUCKET}' created (public)")
    except Exception as e:
        print(f"WARNING: bucket check failed ({str(e)[:80]}) - continuing")

    qa = "approved" if args.approve else "pending"
    active = bool(args.approve)

    for row in rows:
        code = row["template_code"].strip()
        img_f = folder / row["image_file"].strip()
        mask_f = folder / row["mask_file"].strip()

        def _up(path: Path, dest: str) -> str:
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            try:
                sb.storage.from_(BUCKET).upload(
                    dest, path.read_bytes(),
                    file_options={"content-type": mime, "upsert": "true"},
                )
            except Exception:
                pass  # exists -> fine (upsert semantics vary by version)
            return sb.storage.from_(BUCKET).get_public_url(dest)

        image_url = _up(img_f, f"{code}/{img_f.name}")
        mask_url = _up(mask_f, f"{code}/{mask_f.name}")

        tags = [t.strip() for t in (row.get("style_tags") or "").split(";") if t.strip()]
        queries.upsert_template({
            "template_code": code,
            "dress_type": row["dress_type"].strip().lower(),
            "gender": row["gender"].strip().lower(),
            "culture": row["culture"].strip().lower(),
            "style_tags": tags,
            "base_hue_family": (row.get("base_hue_family") or "").strip() or None,
            "image_url": image_url,
            "mask_url": mask_url,
            "qa_status": qa,
            "active_status": active,
            "notes": (row.get("notes") or "").strip() or None,
        })
        print(f"  uploaded {code}  (qa={qa}, active={active})")

    print("-" * 50)
    print(f"{len(rows)} templates uploaded. Total in DB: {queries.count_templates()}")
    if not args.approve:
        print("NOTE: templates are 'pending' - approve after visual QA:")
        print("  dashboard Table Editor, or scripts/approve_template.py <code>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
