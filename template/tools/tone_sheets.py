#!/usr/bin/env python3
"""Build the tone review sheets the user actually looks at.

Three sheets, because one 192-frame grid is unreadable:
  tone-head.png    six outfits: head/shoulder crop, the six complexions plus their source frame
  tone-legs.png    same six outfits, cropped at the feet - where bare legs and shoes live
  tones-men.png / tones-women.png   all 32 outfits at full figure, one row each

The crops are the point. The two defects that every metric in existence blessed were a model's
untanned legs and a tinted patch of backdrop, and both vanish in a 96 px thumbnail of a whole
figure. Look at the crops before saying a batch is right.

  python3 template/tools/tone_sheets.py                 # all three sheets
  python3 template/tools/tone_sheets.py --only M1,W12   # just these, one big row each
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TONES = list(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "tone-ladder.json")))["tones"])
CROPS = {"head": (150, 60, 620, 530), "legs": (100, 856, 670, 1376)}   # fallback only
_CACHE = {}


def crop_for(master_path, name):
    """A crop window measured from THIS figure, not from fixed pixels.

    The absolute windows above were written against M1 and then used on all 32, which is how a review
    sheet ended up showing M4 with his face chopped off - the defect was in the sheet, not in the
    master, and I nearly "fixed" a good image because of it. Figure scale and placement vary per render,
    so the window is anchored to the coded garments: the head box starts 130 rows above the top of the
    clothes (that is where a crown lives on these frames) and the feet box ends 90 rows below the hem
    (that is where soles land). Falls back to the constant if a frame will not classify.
    """
    key = (master_path, name)
    if key in _CACHE:
        return _CACHE[key]
    box = CROPS[name]
    try:
        from mask_code import classify
        arr = np.asarray(Image.open(master_path).convert("RGB"), dtype=float)
        h, w = arr.shape[:2]
        lm, _, _ = classify(arr, ["rose", "blue", "green"])
        coded = lm > 0
        rows = np.nonzero(coded.sum(1) >= 12)[0]
        cols = np.nonzero(coded.any(0))[0]
        if rows.size and cols.size:
            top, bot = int(rows.min()), int(rows.max())
            # Anchor on the whole figure, not the clothes: a crown sits ~180 rows above the top of a
            # jacket, so a window measured from the shoulders cut M4's hair off again even in the fixed
            # sheet. figure() is the same ruler reframe_master audits framing with - one definition.
            try:
                from reframe_master import figure as _fig, manifest as _man
                o = {x["id"]: x for x in _man()}.get(os.path.basename(master_path).split("-")[0])
                f = _fig(arr, o) if o else None
                if f:
                    top, bot = f["rows"]
            except ImportError:
                pass
            x0, x1 = int(cols.min()), int(cols.max())
            if name == "head":
                y0 = max(0, min(top - 40, h - 470))
                box = (x0, y0, x1, min(h, y0 + 470))
            else:
                y1 = min(h, bot + 45)
                box = (x0, max(0, y1 - 520), x1, y1)
    except (OSError, ValueError) as e:      # unreadable master: keep the constant, but say so
        print(f"  crop_for: {master_path} not measurable ({e}) - using the fallback window")
    _CACHE[key] = box
    return box
GAP, TOP, LBL = 6, 26, 12


def font(sz=LBL, bold=True):
    for p in (("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if bold else "",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
    return ImageFont.load_default()


def row(base, oid, slug, scale, crop=None, tag=None, with_source=False, crop_name=""):
    """Cells: the six cards, each labelled. `--with-source` appends base/ as a 7th reference column.

    Off by default on purpose: the shop sells six complexions, and a sheet that shows seven tiles
    invites the answer "seven". `as-shot` IS that source frame (byte-identical), so the reference
    adds nothing a customer needs to see - it stays available for me when I have to judge whether a
    rung actually moved, which is what it was for.
    """
    master = os.path.join(base, "base", slug)
    box = crop_for(master, crop_name) if crop_name else crop

    def load(path):
        if not os.path.exists(path):
            return None
        im = Image.open(path).convert("RGB")
        return im.crop(box) if box else im

    pairs = [(t, load(os.path.join(base, t, slug))) for t in TONES]
    if with_source:
        pairs.append(("source (not a card)", load(os.path.join(base, "base", slug))))
    cells = []
    for name, im in pairs:
        if im is None:
            continue
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.LANCZOS)
        c = Image.new("RGB", (im.width, im.height + 18), (16, 16, 18))
        c.paste(im, (0, 18))
        ImageDraw.Draw(c).text((4, 4), name, fill=(236, 236, 240), font=font())
        cells.append(c)
    if tag and cells:
        t = Image.new("RGB", (72, cells[0].height), (22, 22, 25))
        ImageDraw.Draw(t).text((6, cells[0].height // 2), tag,
                               fill=(244, 244, 248), font=font(14))
        cells = [t] + cells
    return cells


def mount(rows, path, title):
    if not rows:
        return f"{path}: nothing to mount"
    w = max(sum(c.width for c in r) + GAP * max(0, len(r) - 1) for r in rows)
    h = TOP + sum(max(c.height for c in r) + GAP for r in rows) + 6
    out = Image.new("RGB", (w, h), (22, 22, 25))
    d = ImageDraw.Draw(out)
    d.text((8, 5), title, fill=(244, 244, 248), font=font(16))
    y = TOP
    for r in rows:
        x = 8
        for c in r:
            out.paste(c, (x, y))
            x += c.width + GAP
        y += max(c.height for c in r) + GAP
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path, quality=93)
    return f"{os.path.relpath(path, ROOT):34s} {out.width:5d}x{out.height:5d}  {len(rows)} rows"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma list of outfit ids")
    ap.add_argument("--with-source", action="store_true",
                    help="append the master as a 7th reference column (not offered as a card)")
    ap.add_argument("--scale", type=float, default=0.13, help="full-figure sheets")
    ap.add_argument("--crop-scale", type=float, default=0.62, help="close-up sheets")
    a = ap.parse_args()
    base = os.path.join(ROOT, "template")
    man = json.load(open(os.path.join(base, "pieces.json")))
    slug = {o["id"]: o["image"].split("/")[-1] for o in man["outfits"]}
    ids = [x.strip() for x in a.only.split(",") if x.strip()]
    if ids:
        print(mount([row(base, i, slug[i], max(a.crop_scale, 0.55), with_source=a.with_source) for i in ids],
                    os.path.join(base, "_qc", "tone-custom.png"),
                    f"{len(ids)} outfit(s): {len(TONES)} complexions"))
        return 0
    men = [o["id"] for o in man["outfits"] if o["id"].startswith("M")]
    wom = [o["id"] for o in man["outfits"] if o["id"].startswith("W")]
    # A hand-picked sample for the close-up sheets. M1/M3/M5/W2/W12/W17 are the ones that historically
    # carried a defect (untanned legs, a sweep smudge); M4, M9 and W10 are here because their framing was
    # repaired, and a crop sheet is where you see whether a crown actually fits.
    pick = ["M1", "M3", "M4", "M5", "M9", "W2", "W10", "W12", "W17"]
    for name in CROPS:
        rows = [row(base, i, slug[i], a.crop_scale, crop_name=name, tag=f"{i}", with_source=a.with_source)
                for i in pick]
        print(mount(rows, os.path.join(base, "_qc", f"tone-{name}.png"),
                    f"{name.upper()} crop - the {len(TONES)} cards. Check: legs match the face, "
                    "hair unchanged, sweep free of tint"))
    for gname, group in (("tones-men.png", men), ("tones-women.png", wom)):
        rows = [row(base, i, slug[i], a.scale, tag=i, with_source=a.with_source) for i in group]
        print(mount(rows, os.path.join(base, "_qc", gname),
                    f"{len(group)} outfits - {len(TONES)} cards each, full figure"))
    missing = [(t, i) for t in TONES for i in slug
               if not os.path.exists(os.path.join(base, t, slug[i]))]
    print(f"frames present: {len(slug) * len(TONES) - len(missing)}/{len(slug) * len(TONES)}"
          + (f"  MISSING {missing[:6]}" if missing else "  (complete)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
