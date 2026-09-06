"""One review sheet per push batch: a single complexion, all 32 outfits, face and feet.

Why a batch sheet exists: the shop's rule is batch-by-batch with a look in between, and `tone_sheets.py`
answers a different question (does one outfit look right across all six cards). Here the question is
"is this whole folder safe to push" - so every outfit appears twice, head crop over legs crop, and the
measured landing for that frame is printed on it. A batch that passes the eye but has a bad number in
the corner is exactly what the two-row layout is for.

  python3 template/tools/tone_batch.py --tone light-warm
  python3 template/tools/tone_batch.py --tone as-shot --cols 6
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from mask_blue import LADDER, backdrop_like, exclusions, skin_region   # noqa: E402
from mask_code import classify, roles_for                              # noqa: E402
from tone import rgb_to_ls                                             # noqa: E402
from tone_sheets import crop_for, font                     # noqa: E402

HEADS = 4          # rows of head crops = ceil(n/cols); legs crop sits under each head


def landing(tone, ids):
    """Measured skinL/skinS per outfit for this rung, from the run that gated the files."""
    rep = os.path.join(ROOT, "template", "_qc", "tones-report.json")
    out = {}
    if os.path.exists(rep):
        for oid, recs in json.load(open(rep)).items():
            if oid not in ids:
                continue
            for r in recs:
                if r.get("tone") == tone:
                    out[oid] = f"{r.get('skinL', '-')}/{r.get('skinS', '-')}"
    return out


def own_cloth(rgb, o):
    codes = [c for c in ["rose", "blue", "green"] if c in roles_for(o).values()]
    lm, _, _ = classify(rgb.astype(float), codes)
    return lm > 0


def leaks(tone, ids):
    """Per outfit: any owned-cloth pixel or backdrop pixel this folder's frame moved (0 expected)."""
    bad = {}
    raw = {}
    for oid in ids:
        try:
            rgb = np.asarray(Image.open(os.path.join(ROOT, "template", "base", SLUG[oid]))
                             .convert("RGB"), dtype=float)
            z = np.asarray(Image.open(os.path.join(ROOT, "template", tone, SLUG[oid]))
                           .convert("RGB"), dtype=float)
        except FileNotFoundError:
            bad[oid] = "missing"
            raw[oid] = (0, 0)
            continue
        own = own_cloth(rgb, MAN[oid])
        avoid = np.where(own, 255, 0).astype(np.uint8)
        m = skin_region(rgb, avoid)
        d = np.abs(z - rgb).max(2)
        moved = d >= 6                                    # JPEG-safe threshold, as in make_tones
        cloth = int((moved & own).sum())
        sweep = int((moved & backdrop_like(rgb) & ~np.where(
            ndimage.binary_dilation(m, np.ones((3, 3)), iterations=2), 1, 0).astype(bool)).sum()) \
            if moved.any() else 0
        # Same rule make_tones verifies delivered JPEGs with: a re-decoded file differs from its
        # master by a few levels along every hard edge, so a leak only counts past an allowance
        # scaled to lossy delivery (400 px here). Without it this sheet flagged 2-28 px of
        # compression ringing on all 32 outfits as if the tone step had eaten cloth.
        allow = max(400, int(0.0004 * m.size))
        if max(0, cloth - allow) or max(0, sweep - allow):
            bad[oid] = f"cloth {cloth} sweep {sweep} (allowance {allow})"
        raw[oid] = (cloth, sweep)
    return bad, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tone", required=True, help="one rung = one push batch")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--scale", type=float, default=0.26, help="tile scale for the crops")
    ap.add_argument("--full-scale", type=float, default=0.13, help="tile scale for full figures")
    ap.add_argument("--view", default="full,head,legs",
                    help="comma list of grids: full, head, legs")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.tone not in LADDER:
        print(f"FAIL: {a.tone!r} is not a rung. Available: {', '.join(LADDER)}")
        return 2
    global SLUG, MAN
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    MAN = {o["id"]: o for o in man["outfits"]}
    SLUG = {o["id"]: o["image"].split("/")[-1] for o in man["outfits"]}
    ids = list(SLUG)
    vals = landing(a.tone, ids)
    bad, raw = leaks(a.tone, ids)

    n = len([p for p in os.listdir(os.path.join(ROOT, "template", a.tone)) if p.endswith(".jpg")])

    # Two grids stacked: all 32 head crops, then the same 32 outfits' feet. Side-by-side per outfit
    # made the sheet 5200 px tall and unreadable; stacked grids keep the pair legible and put the
    # comparison (does the leg match the face?) in the same scroll. Tiles are built here rather than
    # through tone_sheets.row(), which returns [tag, tile] - this layout wants one cell per outfit
    # with the label already drawn on it.
    def tile(oid, cname):
        im0 = Image.open(os.path.join(ROOT, "template", a.tone, SLUG[oid])).convert("RGB")
        # "full" is the frame itself: the codes on these masters are how the pieces were masked, and
        # a preview that only shows crops hides them. A batch is confirmed on what ships, so the whole
        # figure goes on the sheet first and the crops come under it as the detail pass.
        # same figure-relative window the tone sheets use: an absolute box cropped M4's face off in
        # a preview and made a healthy master look defective
        im = im0 if cname == "full" else im0.crop(
            crop_for(os.path.join(ROOT, "template", "base", SLUG[oid]), cname))
        sc = a.full_scale if cname == "full" else a.scale
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
        cell = Image.new("RGB", (im.width, im.height + 16), (18, 18, 20))
        cell.paste(im, (0, 16))
        ImageDraw.Draw(cell).text((3, 3), f"{oid} {vals.get(oid, '-')}",
                                  fill=(240, 240, 244), font=font(12))
        return cell

    grids = []
    for cname in a.view.split(","):
        grow = [[tile(oid, cname) for oid in ids[i:i + a.cols]]
                for i in range(0, len(ids), a.cols)]
        grids.append((cname, grow))

    pad, top = 6, 24
    w = max(sum(c.width for c in r) + pad * (len(r) - 1) for _, g in grids for r in g)
    h = sum(top + sum(max(c.height for c in r) + pad for r in g) + 6 for _, g in grids)
    out_im = Image.new("RGB", (w, h), (18, 18, 20))
    d = ImageDraw.Draw(out_im)
    y = 0
    for cname, g in grids:
        d.text((8, y + 5), f"{cname}: {n}/32 frames of {a.tone}   "
                          "(label = outfit + measured skin L/S)",
               fill=(244, 244, 248), font=font(15))
        y += top
        for r in g:
            x = 8
            for c in r:
                out_im.paste(c, (x, y))
                x += c.width + pad
            y += max(c.height for c in r) + pad
        y += 6
    out = a.out or os.path.join(ROOT, "template", "_qc", f"batch-{a.tone}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    out_im.save(out, quality=92)
    print(f"{os.path.relpath(out, ROOT)}  {out_im.width}x{out_im.height}  "
          f"grids: {a.view}  ({len(grids[0][1])} rows x {a.cols})")
    print(f"  frames in folder: {n}/32   landings read from the report: {len(vals)}/32"
          + ("  <- REPORT IS PARTIAL, re-run make_tones --verify-only over everything"
             if len(vals) < len(ids) else ""))
    worst = max(raw.values(), key=lambda t: max(t), default=(0, 0))
    if bad:
        print(f"  LEAKS past the JPEG allowance: {bad}")
    else:
        print(f"  cloth/backdrop movement: worst outfit {worst[0]}/{worst[1]} px, all inside the "
              f"400 px ringing allowance   (all {len(ids)} outfits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
