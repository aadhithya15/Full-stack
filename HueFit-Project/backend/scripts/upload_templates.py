"""Validate and upload prepared HueFit templates to Supabase.

Supports up to three semantic garment masks and either the latest six native
complexion variants or the earlier eight public-key variants.
Uploads are serialized, retried, and verified by listing the destination
folder before a public URL is accepted.
"""
from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

VALID_GENDERS = {"male", "female", "unisex"}
VALID_CULTURES = {"tamil", "western", "fusion"}
PUBLIC_TONES = {"fair", "light", "wheatish", "medium", "dusky", "deep", "warm", "cool"}
NATIVE_TONES = {"fair", "light-warm", "light-tan", "medium-brown", "deep", "ebony"}
VALID_TONES = PUBLIC_TONES | NATIVE_TONES
VALID_TONE_SETS = (PUBLIC_TONES, NATIVE_TONES)
BUCKET = "templates"
UPLOAD_ATTEMPTS = 3
_UPLOAD_LOCK = threading.Lock()


def _parse_tones(row: dict[str, str]) -> dict[str, str]:
    raw = (row.get("tone_variants") or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"bad tone_variants JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("tone_variants must be a JSON object")
    result = {
        str(tone).strip().lower(): str(filename).strip()
        for tone, filename in value.items()
        if str(filename).strip()
    }
    unknown = set(result) - VALID_TONES
    if unknown:
        raise ValueError("unknown tones: " + ", ".join(sorted(unknown)))
    return result


def _mask_files(row: dict[str, str]) -> list[str]:
    return [
        value
        for value in (
            (row.get("mask_file") or "").strip(),
            (row.get("mask2_file") or "").strip(),
            (row.get("mask3_file") or "").strip(),
        )
        if value
    ]


def validate_row(row: dict[str, str], folder: Path, line: int) -> tuple[list[str], dict]:
    problems: list[str] = []
    info: dict[str, Any] = {}
    code = (row.get("template_code") or "").strip()
    prefix = f"row {line}" + (f" ({code})" if code else "")

    if not code:
        problems.append("missing template_code")
    if (row.get("gender") or "").strip().lower() not in VALID_GENDERS:
        problems.append(f"bad gender '{row.get('gender')}'")
    if (row.get("culture") or "").strip().lower() not in VALID_CULTURES:
        problems.append(f"bad culture '{row.get('culture')}'")
    if not (row.get("dress_type") or "").strip():
        problems.append("missing dress_type")

    image_name = (row.get("image_file") or "").strip()
    image_path = folder / image_name
    if not image_name or not image_path.is_file():
        problems.append(f"image not found: {image_name}")

    masks = _mask_files(row)
    if not masks:
        problems.append("at least mask_file is required")
    for name in masks:
        if not (folder / name).is_file():
            problems.append(f"mask not found: {name}")

    try:
        tones = _parse_tones(row)
    except ValueError as exc:
        tones = {}
        problems.append(str(exc))
    if tones and set(tones) not in VALID_TONE_SETS:
        problems.append(
            "tone_variants must contain all six native tones or all eight public tones"
        )
    for tone, name in tones.items():
        if not (folder / name).is_file():
            problems.append(f"{tone} variant not found: {name}")

    if problems:
        return [f"{prefix}: {problem}" for problem in problems], info

    try:
        with Image.open(image_path) as opened:
            image_size = opened.size
            opened.verify()
    except Exception as exc:
        return [f"{prefix}: cannot open base image ({exc})"], info

    coverages: list[float] = []
    mask_arrays: list[np.ndarray] = []
    for name in masks:
        try:
            with Image.open(folder / name) as opened:
                mask = opened.convert("L")
                if mask.size != image_size:
                    problems.append(
                        f"size mismatch: {name} is {mask.size}, base is {image_size}"
                    )
                    continue
                array = np.asarray(mask, dtype=np.uint8)
                histogram = mask.histogram()
        except Exception as exc:
            problems.append(f"cannot open mask {name} ({exc})")
            continue

        total = sum(histogram)
        non_binary = total - histogram[0] - histogram[255]
        coverage = histogram[255] / max(1, total)
        coverages.append(coverage)
        mask_arrays.append(array >= 128)
        if non_binary:
            problems.append(f"{name} has {non_binary} non-binary pixels")
        if coverage < 0.005:
            problems.append(f"{name} covers only {coverage:.2%}")
        if coverage > 0.90:
            problems.append(f"{name} covers {coverage:.1%}; mask may be inverted")

    if len(mask_arrays) > 1:
        ownership = np.zeros(mask_arrays[0].shape, dtype=np.uint8)
        for array in mask_arrays:
            ownership += array.astype(np.uint8)
        overlap = int((ownership > 1).sum())
        if overlap:
            problems.append(f"garment masks overlap by {overlap} pixels")

    for tone, name in tones.items():
        try:
            with Image.open(folder / name) as opened:
                if opened.size != image_size:
                    problems.append(
                        f"{tone} variant size {opened.size} does not match {image_size}"
                    )
        except Exception as exc:
            problems.append(f"cannot open {tone} variant {name} ({exc})")

    info["coverages"] = coverages
    info["tones"] = len(tones)
    return [f"{prefix}: {problem}" for problem in problems], info


def validate_pair(row: dict, folder: Path, line: int) -> tuple[list[str], dict]:
    """Backward-compatible validator used by the original unit tests.

    The production validator supports small secondary pieces down to 0.5%,
    while this legacy one-pair interface keeps its original 3% rule.
    """
    problems: list[str] = []
    info: dict[str, Any] = {}
    code = (row.get("template_code") or "").strip()
    if not code:
        problems.append("missing template_code")
    if (row.get("gender") or "").strip().lower() not in VALID_GENDERS:
        problems.append(f"bad gender '{row.get('gender')}'")
    if (row.get("culture") or "").strip().lower() not in VALID_CULTURES:
        problems.append(f"bad culture '{row.get('culture')}'")
    if not (row.get("dress_type") or "").strip():
        problems.append("missing dress_type")

    image_path = folder / (row.get("image_file") or "").strip()
    mask_path = folder / (row.get("mask_file") or "").strip()
    if not image_path.name or not image_path.exists():
        problems.append(f"image not found: {image_path.name}")
    if not mask_path.name or not mask_path.exists():
        problems.append(f"mask not found: {mask_path.name}")
    if problems:
        return [f"row {line}: {problem}" for problem in problems], info

    try:
        image = Image.open(image_path)
        mask = Image.open(mask_path).convert("L")
    except Exception as exc:
        return [f"row {line}: cannot open images ({exc})"], info

    if image.size != mask.size:
        problems.append(
            f"size mismatch: image {image.size[0]}x{image.size[1]} vs "
            f"mask {mask.size[0]}x{mask.size[1]}"
        )
    else:
        histogram = mask.histogram()
        total = sum(histogram)
        dark = sum(histogram[:32])
        bright = sum(histogram[224:])
        middle = total - dark - bright
        if middle / max(1, total) > 0.20:
            problems.append("mask not binary enough")
        coverage = bright / max(1, total)
        info["coverage"] = coverage
        if coverage < 0.03:
            problems.append(f"mask covers only {coverage:.1%} - is it empty?")
        elif coverage > 0.90:
            problems.append(f"mask covers {coverage:.0%} - is it inverted?")

    return [f"row {line}: {problem}" for problem in problems], info


def _object_name(item: Any) -> str | None:
    if isinstance(item, dict):
        return item.get("name")
    return getattr(item, "name", None)


def _object_exists(bucket: Any, destination: str) -> bool:
    folder, name = destination.rsplit("/", 1) if "/" in destination else ("", destination)
    try:
        items = bucket.list(folder)
    except Exception:
        return False
    return isinstance(items, list) and any(_object_name(item) == name for item in items)


def _upload_file(bucket: Any, source: Path, destination: str) -> str:
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    data = source.read_bytes()
    last_error = "object was not visible after upload"

    with _UPLOAD_LOCK:
        for attempt in range(1, UPLOAD_ATTEMPTS + 1):
            try:
                bucket.upload(
                    destination,
                    data,
                    file_options={"content-type": mime, "upsert": "true"},
                )
            except Exception as upload_exc:
                last_error = str(upload_exc)
                # Some storage versions reject upload-on-existing despite the
                # upsert flag. update() is the safe idempotent fallback.
                try:
                    bucket.update(
                        destination,
                        data,
                        file_options={"content-type": mime, "upsert": "true"},
                    )
                except Exception as update_exc:
                    last_error = f"upload={upload_exc}; update={update_exc}"

            if _object_exists(bucket, destination):
                return bucket.get_public_url(destination)
            if attempt < UPLOAD_ATTEMPTS:
                time.sleep(0.2 * attempt)

    raise RuntimeError(
        f"upload failed after {UPLOAD_ATTEMPTS} attempts for {destination}: {last_error}"
    )


def _ensure_bucket(storage: Any) -> Any:
    buckets = storage.list_buckets()
    names = {_object_name(bucket) for bucket in buckets}
    if BUCKET not in names:
        storage.create_bucket(BUCKET, options={"public": True})
        print(f"bucket '{BUCKET}' created (public)")
    return storage.from_(BUCKET)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="prepared folder containing templates.csv")
    parser.add_argument("--dry-run", action="store_true", help="validate only")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="mark rows approved and active immediately (use only after visual QA)",
    )
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    csv_path = folder / "templates.csv"
    if not csv_path.is_file():
        print(f"ERROR: {csv_path} not found")
        return 1

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print("ERROR: templates.csv is empty")
        return 1

    print(f"folder: {folder}")
    print(f"templates: {len(rows)}")

    all_problems: list[str] = []
    infos: dict[str, dict] = {}
    for line, row in enumerate(rows, start=2):
        problems, info = validate_row(row, folder, line)
        all_problems.extend(problems)
        infos[(row.get("template_code") or f"row-{line}").strip()] = info

    if all_problems:
        print("VALIDATION FAILED:")
        for problem in all_problems:
            print("  -", problem)
        return 1

    print("validation: all files structurally valid")
    for code, info in infos.items():
        coverage = ",".join(f"{value:.1%}" for value in info.get("coverages", []))
        print(f"  {code:28} masks={coverage} tones={info.get('tones', 0)}")

    if args.dry_run:
        print("DRY RUN - nothing uploaded")
        return 0

    from app.db import queries
    from app.db.supabase_client import get_supabase

    try:
        bucket = _ensure_bucket(get_supabase().storage)
    except Exception as exc:
        print(f"ERROR: storage setup failed: {exc}")
        return 1

    qa_status = "approved" if args.approve else "pending"
    active = bool(args.approve)

    for row in rows:
        code = row["template_code"].strip()
        try:
            image_name = row["image_file"].strip()
            image_url = _upload_file(bucket, folder / image_name, f"{code}/{image_name}")

            mask_urls: list[str] = []
            for name in _mask_files(row):
                mask_urls.append(_upload_file(bucket, folder / name, f"{code}/{name}"))
            mask_urls += [""] * (3 - len(mask_urls))

            tone_urls: dict[str, str] = {}
            for tone, name in _parse_tones(row).items():
                tone_urls[tone] = _upload_file(
                    bucket,
                    folder / name,
                    f"{code}/tones/{name}",
                )

            tags = [
                tag.strip()
                for tag in (row.get("style_tags") or "").split(";")
                if tag.strip()
            ]
            queries.upsert_template(
                {
                    "template_code": code,
                    "dress_type": row["dress_type"].strip().lower(),
                    "gender": row["gender"].strip().lower(),
                    "culture": row["culture"].strip().lower(),
                    "style_tags": tags,
                    "base_hue_family": (row.get("base_hue_family") or "").strip() or None,
                    "image_url": image_url,
                    "mask_url": mask_urls[0],
                    "mask2_url": mask_urls[1] or None,
                    "mask3_url": mask_urls[2] or None,
                    "tone_variants": tone_urls,
                    "qa_status": qa_status,
                    "active_status": active,
                    "notes": (row.get("notes") or "").strip() or None,
                }
            )
            print(
                f"  uploaded {code:28} masks={len(_mask_files(row))} "
                f"tones={len(tone_urls)} qa={qa_status}"
            )
        except Exception as exc:
            print(f"ERROR: {code} failed: {type(exc).__name__}: {exc}")
            print("Check that migrations 009 and 010 were run, then rerun safely.")
            return 1

    print("-" * 64)
    print(f"{len(rows)} templates uploaded. Total DB rows: {queries.count_templates()}")
    if not args.approve:
        print("Rows are pending. Approve only after visual QA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
