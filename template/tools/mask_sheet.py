#!/usr/bin/env python3
"""Contact sheet of every finished outfit with its piece masks colour-coded.

This is the artefact to review the masking by eye: each cell is the base frame
with one flat colour per garment piece, so a wrong boundary, a missing sleeve
or a mask that ate the neck shows up immediately. Scratch only - _qc/ is
gitignored, it is never shipped.

    python3 template/tools/mask_sheet.py [--cols 8] [--out template/_qc/masks-all.png]
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TPL = os.path.join(ROOT, "template")
PAL = [(232, 76, 61), (58, 148, 220), (66, 190, 110), (240, 180, 60),
       (170, 110, 225), (240, 120, 180), (120, 200, 210)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--w", type=int, default=260)
    ap.add_argument("--out", default="template/_qc/masks-all.png")
    ap.add_argument("--all", action="store_true", help="include outfits whose masks are incomplete")
    a = ap.parse_args()

    man = json.load(open(os.path.join(TPL, "pieces.json")))
    have = {os.path.basename(p) for p in glob.glob(os.path.join(TPL, "universal-masking", "*.png"))}
    cells = []
    for o in man["outfits"]:
        base = os.path.join(TPL, o["image"])
        if not os.path.exists(base):
            alt = sorted(glob.glob(os.path.join(TPL, "base", o["id"] + "-*.jpg")))
            if not alt:
                continue
            base = alt[0]
        pieces = [p for p in o["pieces"] if f"{o['id']}-{p['piece']}-mask.png" in have]
        if not pieces or (not a.all and len(pieces) != len(o["pieces"])):
            continue
        B = np.asarray(Image.open(base).convert("RGB"), dtype=np.uint8).copy()
        for i, p in enumerate(pieces):
            m = np.asarray(Image.open(os.path.join(TPL, "universal-masking",
                                                   f"{o['id']}-{p['piece']}-mask.png")).convert("L")) > 127
            c = np.array(PAL[i % len(PAL)], dtype=np.uint8)
            B[m] = (0.42 * c + 0.58 * B[m]).astype(np.uint8)
        im = Image.fromarray(B).resize((a.w, int(a.w * 1376 / 768)), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.width - 1, 0], fill=(0, 0, 0))
        tags = "  ".join(f"{p['piece']}" for p in pieces)
        box = d.textbbox((0, 0), tags)
        d.rectangle([0, im.height - 30, im.width, im.height], fill=(20, 20, 20))
        d.text((4, im.height - 28), f"{o['id']} {o['name'][:30]}", fill=(255, 255, 255))
        d.text((4, im.height - 15), tags[:58], fill=(200, 230, 200))
        cells.append(im)
    if not cells:
        print("nothing to draw", file=sys.stderr)
        return 1
    cw, ch = cells[0].width, max(c.height for c in cells)
    cols = min(a.cols, len(cells))
    rows = (len(cells) + cols - 1) // cols
    pad = 8
    sheet = Image.new("RGB", (cols * cw + (cols + 1) * pad, rows * ch + (rows + 1) * pad + 34), (250, 250, 250))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), f"{len(cells)} outfits - each flat colour is one garment mask "
                     f"(all 6 skin tones share these)", fill=(20, 20, 20))
    for i, c in enumerate(cells):
        r, k = divmod(i, cols)
        sheet.paste(c, (pad + k * (cw + pad), pad + 34 + r * (ch + pad)))
    out = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print(f"wrote {a.out}  ({len(cells)} outfits, {sheet.size[0]}x{sheet.size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
