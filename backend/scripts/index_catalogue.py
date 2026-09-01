"""HueFit v2 - OFFLINE catalogue indexer.

Reads a catalogue folder (CSV + images), and for every product:
  1. CLIP-embeds the photo          -> 512 map coordinates
  2. extracts dominant colour       -> hex + hue family (colour law input)
  3. optional Gemini auto-tags      -> extra tags (skipped in mock mode)
  4. uploads photo to the PUBLIC 'product-images' bucket -> permanent URL
  5. upserts the product row into Supabase

Usage (from backend-inspect, venv active):
    python scripts/index_catalogue.py catalogue/starter
    python scripts/index_catalogue.py catalogue/starter --client my-shop
    python scripts/index_catalogue.py catalogue/starter --dry-run

Catalogue folder layout:
    catalogue/starter/
      products.csv        (see scripts/catalogue_template.csv for columns)
      images/
        p001.jpg          (filename referenced by the CSV 'image_file' column)
        ...

CSV columns:
  title,gender,dress_type,culture,occasions,price,image_file,buy_url,color_hex,hue_family,tags
  - occasions and tags: semicolon-separated lists (festive;wedding)
  - buy_url: LEAVE EMPTY for now (placeholder policy until real clients)
  - color_hex / hue_family: optional - if given, they WIN over the extractor
Safe to re-run: existing products (same client+title) are updated, not duplicated.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VALID_GENDERS = {"male", "female", "unisex"}
VALID_CULTURES = {"tamil", "western", "fusion"}


def load_rows(folder: Path) -> list[dict]:
    csv_path = folder / "products.csv"
    if not csv_path.exists():
        sys.exit(f"ERROR: {csv_path} not found")
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("ERROR: products.csv is empty")
    return rows


def validate(row: dict, folder: Path, line: int) -> list[str]:
    problems = []
    if not (row.get("title") or "").strip():
        problems.append("missing title")
    if (row.get("gender") or "").strip().lower() not in VALID_GENDERS:
        problems.append(f"bad gender '{row.get('gender')}'")
    if (row.get("culture") or "").strip().lower() not in VALID_CULTURES:
        problems.append(f"bad culture '{row.get('culture')}'")
    img = (row.get("image_file") or "").strip()
    if not img:
        problems.append("missing image_file")
    elif not (folder / "images" / img).exists():
        problems.append(f"image not found: images/{img}")
    return [f"row {line}: {p}" for p in problems]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="catalogue folder containing products.csv + images/")
    ap.add_argument("--client", default="starter", help="catalogue client name (default: starter)")
    ap.add_argument("--dry-run", action="store_true", help="validate + embed only; no uploads")
    ap.add_argument("--no-tags", action="store_true", help="skip Gemini auto-tagging")
    args = ap.parse_args()

    folder = Path(args.folder)
    rows = load_rows(folder)
    print(f"catalogue: {folder}  |  products: {len(rows)}  |  client: {args.client}")

    # ---- validate everything BEFORE any slow work ----
    problems = []
    for i, row in enumerate(rows, start=2):
        problems += validate(row, folder, i)
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("validation: all rows OK")

    from PIL import Image

    from app.services.clip_service import embed_image, model_info
    from app.services.color_extract import extract_dominant

    print(f"CLIP: {model_info()['model']} / {model_info()['pretrained']}")

    # optional Gemini tagging (graceful skip in mock mode / --no-tags)
    tagger = None
    if not args.no_tags:
        try:
            from app.config import Config
            if not Config.ai_mock_mode():
                from app.services.auto_tags import suggest_tags  # Phase V2-2b optional
                tagger = suggest_tags
        except Exception:
            tagger = None
    if tagger is None:
        print("auto-tags: OFF (mock mode or --no-tags) - CSV tags used as-is")

    if not args.dry_run:
        from app.db import queries
        from app.db.supabase_client import get_supabase
        sb = get_supabase()
        client = queries.get_or_create_client(args.client)
        print(f"supabase client row: {client['id'][:8]}...")

    t_start = time.time()
    done = 0
    for row in rows:
        title = row["title"].strip()
        img_path = folder / "images" / row["image_file"].strip()
        image = Image.open(img_path)

        t0 = time.time()
        embedding = embed_image(image)
        embed_ms = (time.time() - t0) * 1000

        # colour: CSV metadata wins; extractor is the fallback
        hexcode = (row.get("color_hex") or "").strip()
        family = (row.get("hue_family") or "").strip()
        if not hexcode or not family:
            ex_hex, ex_fam = extract_dominant(image)
            hexcode = hexcode or ex_hex
            family = family or ex_fam

        tags = [t.strip() for t in (row.get("tags") or "").split(";") if t.strip()]
        if tagger:
            try:
                tags = sorted(set(tags) | set(tagger(image, title)))
            except Exception:
                pass

        occasions = [o.strip().lower() for o in (row.get("occasions") or "").split(";") if o.strip()]
        buy_url = (row.get("buy_url") or "").strip() or None  # placeholder policy

        print(f"  {title[:44]:46} {family:14} embed {embed_ms:5.0f}ms")

        if args.dry_run:
            done += 1
            continue

        # upload photo -> permanent public URL
        storage_path = f"{args.client}/{img_path.name}"
        raw = img_path.read_bytes()
        mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
        try:
            sb.storage.from_("product-images").upload(
                storage_path, raw, file_options={"content-type": mime, "upsert": "true"}
            )
        except Exception:
            pass  # already exists with upsert disabled server-side -> fine
        public_url = sb.storage.from_("product-images").get_public_url(storage_path)

        queries.upsert_product(
            client["id"],
            {
                "title": title,
                "gender": row["gender"].strip().lower(),
                "dress_type": (row.get("dress_type") or "other").strip().lower(),
                "culture": row["culture"].strip().lower(),
                "occasions": occasions,
                "dominant_hex": hexcode,
                "hue_family": family,
                "tags": tags,
                "price": float(row["price"]) if (row.get("price") or "").strip() else None,
                "image_url": public_url,
                "buy_url": buy_url,
                "embedding": embedding,
                "indexed_at": "now()",
                "in_stock": True,
            },
        )
        done += 1

    dt = time.time() - t_start
    mode = "DRY RUN - nothing uploaded" if args.dry_run else "uploaded to Supabase"
    print("-" * 60)
    print(f"{done}/{len(rows)} products processed in {dt:.1f}s ({mode})")
    if not args.dry_run:
        from app.db import queries as q
        print(f"total products for client '{args.client}': {q.count_products(client['id'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
