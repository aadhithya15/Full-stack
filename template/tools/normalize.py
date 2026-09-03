"""Fit a generated frame onto the catalogue canvas, loss-controlled, in one pass only.

The image generator returns 9:16 at whatever native size it likes (observed: 941x1672). The mask/overlay
system is pixel-locked, so every frame in the catalogue must share one canvas: 768x1376.

Order matters: centre-crop to the exact target aspect first (only if the source aspect differs by more
than 0.3% -- a native 9:16 frame needs no crop), THEN one LANCZOS downscale, then encode once at
quality 95 with no chroma subsampling so the grey field does not gain blocky colour ringing.

Also writes a contact sheet of every file it touched so a human eye can check what the numeric gates
cannot see (framing, dead hands, wrong garment, hair over the shoulder).

Usage: python3 template/tools/normalize.py <src-dir> <dst-dir> [--sheet out.png]
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image

TW, TH = 768, 1376


def fit(src, dst):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    ar, tar = w / h, TW / TH
    crop_log = "no-crop"
    if abs(ar / tar - 1) > 0.003:                       # aspect off: trim width or height to match
        if ar > tar:
            nw = int(round(h * tar))
            x0 = (w - nw) // 2
            im = im.crop((x0, 0, x0 + nw, h))
        else:
            nh = int(round(w / tar))
            y0 = (h - nh) // 2                          # centre-crop; keeps head and feet when margins are even
            im = im.crop((0, y0, w, y0 + nh))
        crop_log = f"crop {w}x{h}->{im.size[0]}x{im.size[1]}"
    if im.size != (TW, TH):
        im = im.resize((TW, TH), Image.LANCZOS)
    im.save(dst, quality=95, subsampling=0, optimize=False)
    return crop_log, (w, h)


def sheet(files, out, cols=5, tile_h=360):
    if not files:
        return
    th = tile_h
    tw = int(round(th * TW / TH))
    rows = (len(files) + cols - 1) // cols
    sheetim = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + 20) + 6), (32, 32, 32))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheetim)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS)
        x = 6 + (i % cols) * (tw + 6)
        y = 6 + (i // cols) * (th + 20)
        sheetim.paste(im, (x, y))
        d.text((x + 2, y + th + 3), os.path.basename(f).replace(".jpg", "")[:26], fill=(230, 230, 230))
    sheetim.save(out)
    print(f"contact sheet -> {out}  ({sheetim.size[0]}x{sheetim.size[1]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--sheet", default="")
    a = ap.parse_args()
    os.makedirs(a.dst, exist_ok=True)
    done = []
    for p in sorted(glob.glob(os.path.join(a.src, "*.jpg")) + glob.glob(os.path.join(a.src, "*.png"))):
        o = os.path.join(a.dst, os.path.splitext(os.path.basename(p))[0] + ".jpg")
        log, orig = fit(p, o)
        sz = os.path.getsize(o) / 1024
        print(f"  {os.path.basename(p):34s} {orig[0]}x{orig[1]} {log:24s} -> 768x1376  {sz:5.0f} KB")
        done.append(o)
    if a.sheet:
        sheet(done, a.sheet)


if __name__ == "__main__":
    main()
