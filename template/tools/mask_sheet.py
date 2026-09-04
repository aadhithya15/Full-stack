"""Build the visual proof the masks have to be shown in, not described.

    python3 template/tools/mask_sheet.py

Writes template/_qc/masks-proof.png: one row per outfit - the master with every
piece-mask boundary drawn over it, then each piece mask on its own with its area.
Also re-runs mask_code --sheet so code-proof.png (the colour-coded masters at
working resolution) is never older than the masks.

This exists because "0 error" is a claim about numbers; the user asked to see the
result. A sheet is also the cheapest way to catch a whole class of bug that every
gate in mask_code.py is blind to: a mask that is geometrically perfect and owns the
wrong garment. Area arithmetic cannot see mis-ownership, colour can.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TINT = {"rose": (232, 60, 170), "blue": (50, 120, 240), "green": (50, 190, 90)}
EDGE = {"rose": (255, 60, 200), "blue": (80, 160, 255), "green": (80, 255, 140)}


def font(px, bold=False):
    path = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    try:
        return ImageFont.truetype(path, px)
    except Exception:
        return ImageFont.load_default()


def load(oid, man):
    o = {x["id"]: x for x in man["outfits"]}[oid]
    base = os.path.join(ROOT, "template", o["image"])
    rgb = np.array(Image.open(base).convert("RGB"), dtype=np.uint8)
    masks = []
    for p in o["pieces"]:
        fp = os.path.join(ROOT, "template", "universal-masking", f"{oid}-{p['piece']}-mask.png")
        m = np.asarray(Image.open(fp), dtype=np.uint8) > 127
        masks.append((p["piece"], p.get("code") or "rose", m))
    return o, rgb, masks


def build(ids, out, scale=0.30):
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    F, Fs = font(15, True), font(13)
    W, H = 768, 1376
    cw, ch = int(W * scale), int(H * scale)
    pad, lab = 8, 20
    rows = []
    for oid in ids:
        o, rgb, masks = load(oid, man)
        cells = []
        for nm, code, m in masks:                      # one cell per piece mask
            vis = np.full(rgb.shape, 46.0)
            vis[m] = np.array(TINT.get(code, TINT["rose"]), float)
            if m.any():
                vis[m & ~ndimage.binary_erosion(m, np.ones((3, 3)))] = 255.0
            im = Image.fromarray(np.clip(vis, 0, 255).astype(np.uint8))
            ImageDraw.Draw(im).text((6, 4), f"{nm} {int(m.sum()) // 1000}k", font=Fs,
                                    fill=(235, 235, 235))
            cells.append(im)
        a = rgb.astype(np.uint8).copy()                 # master + boundaries
        for nm, code, m in masks:
            if not m.any():
                continue
            a[m] = (a[m] * 0.5 + np.array(TINT.get(code, TINT["rose"])) * 0.5).astype(np.uint8)
            a[m & ~ndimage.binary_erosion(m, np.ones((3, 3)))] = EDGE.get(code, EDGE["rose"])
        im = Image.fromarray(a)
        ImageDraw.Draw(im).text((6, 4), f"{oid}  {o['slug']}", font=F, fill=(255, 255, 255))
        rows.append([im] + cells)
    ncol = max(len(r) for r in rows)
    sheet = Image.new("RGB", (ncol * (cw + pad) + pad, len(rows) * (ch + lab + pad) + 24),
                      (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 6), "HueFit - left: master with each piece mask tinted and its boundary drawn. "
                     "right: every mask on its own, with pixel count", font=Fs, fill=(225, 225, 225))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im.resize((cw, ch), Image.LANCZOS),
                        (pad + c * (cw + pad), 24 + lab + r * (ch + lab + pad)))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return sheet.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default=os.path.join(ROOT, "template", "_qc", "masks-proof.png"))
    ap.add_argument("--scale", type=float, default=0.30,
                    help="cell width as a fraction of 768; raise it to inspect one batch")
    a = ap.parse_args()
    if a.ids:
        ids = a.ids.split(",")
    else:
        man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
        ids = sorted((o["id"] for o in man["outfits"] if o.get("status") in ("masked", "tone+mask")),
                     key=lambda q: (q[0], int(q[1:])))
    if not ids:
        print("nothing masked yet", file=sys.stderr)
        return 1
    print("sheet", build(ids, a.out, scale=a.scale), "->", os.path.relpath(a.out, ROOT))
    if a.scale != 0.30:
        print("sheet only: skipping the full re-run")
        return 0
    r = subprocess.run([sys.executable, os.path.join(ROOT, "template", "tools", "mask_code.py"),
                        "--sheet", os.path.join(ROOT, "template", "_qc", "code-proof.png")],
                       capture_output=True, text=True)
    print((r.stdout or "").strip().splitlines()[-1] if r.stdout else r.stderr.strip()[-200:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
