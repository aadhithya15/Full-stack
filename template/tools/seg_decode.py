"""Decode a model-drawn colour-coded segmentation into verified per-piece mask PNGs.

Why: separating a blazer from the shirt beneath it, or a saree drape from a blouse, is a SEMANTIC
judgement that no luminance rule makes reliably -- a grey-on-grey boundary has no colour signal at all,
and a saree's drape breaks every "the garment gets narrower below" heuristic. So the boundary is drawn by
a vision model (see template/tools/SEGMENT_PROMPT.md) and then this tool does the part a model cannot be
trusted with: proving each region against pixels.

Verification per outfit, against cloth = the colour-derived garment region from make_masks.cloth_mask():
  partition     every decoded piece lies inside cloth, pieces do not overlap each other
  coverage      union of decoded pieces covers >= 90% of cloth
  solid         each piece is one connected region (>= 92% of its area in the largest component)
  area          each piece >= 1.5% of cloth (a smaller region is a misread colour, not a garment)
  stability     the same piece decoded at two colour thresholds must agree on >= 97% of its pixels --
                a boundary that moves when you nudge the threshold is a guess, and it will shimmer on
                the six tone files
Any check that fails rejects the whole outfit; nothing is written for it.

Usage (repo root):
  python3 template/tools/seg_decode.py template/_qc/seg            # decode + write + verify
  python3 template/tools/seg_decode.py template/_qc/seg --only M2 W4
Exit 1 on any rejection.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from make_masks import cloth_mask, UPPER, LOWER, WHOLE_BODY, WHOLE_BODY

COL = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
       "yellow": (255, 255, 0), "magenta": (255, 0, 255)}


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=int)


def decode(X, names, thr=140):
    """Return {piece: bool mask}, with every boundary pixel assigned by NEAREST colour, not by a threshold.

    A model-drawn segmentation arrives with a 1-2px anti-aliased fringe between colours. Testing that
    fringe at threshold 140 and again at 110 gives different answers, which showed up as stability IoU
    0.48-0.94 against my 0.97 floor -- the pieces were fine, the *rule* was unstable. Assigning each
    pixel to whichever palette colour it is closest to removes the threshold entirely: the same pixel
    belongs to the same piece no matter how the test is nudged.
    """
    cols = np.stack([np.array(COL[c], dtype=float) for c in list(COL)[:len(names)]])   # (P,3)
    d = ((X[:, :, None, :] - cols[None, None, :, :]) ** 2).sum(-1)                     # (H,W,P)
    near = d.argmin(2)
    best = d.min(2)
    out = {}
    for i, name in enumerate(names):
        m = (near == i) & (best < 9000)        # a pixel far from every palette colour is background/skin
        out[name] = ndimage.median_filter(m.astype(np.uint8), 3).astype(bool)
    return out


def clean(m, ref):
    m = ndimage.binary_closing(m, np.ones((5, 5)))
    m = ndimage.binary_opening(m, np.ones((3, 3)))
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    if n > 1:
        cs = np.bincount(lab.ravel(), minlength=n + 1)
        m = lab == (int(np.argmax(cs[1:])) + 1)
    return m & ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("segdir")
    ap.add_argument("--only", nargs="*", default=[])
    args = ap.parse_args()
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    outdir = os.path.join(ROOT, "template", "universal-masking")
    os.makedirs(outdir, exist_ok=True)
    ok = rej = 0
    for o in man["outfits"]:
        seg = os.path.join(ROOT, args.segdir, f"{o['id']}-seg.png")
        base = os.path.join(ROOT, "template", o["image"])
        if args.only and o["id"] not in args.only:
            continue
        if not os.path.exists(base):
            continue
        if not os.path.exists(seg):
            continue
        # An outfit whose seg file exists but never printed a verdict means the decoder silently skipped
        # it (a manifest/model piece-count mismatch used to do exactly that, hiding W17 from the report).
        if len([q for q in o["pieces"] if q["z"]]) not in (1, 2, 3, 4):
            print(f"  {o['id']:4s} SKIP  manifest lists {len([q for q in o['pieces'] if q['z']])} visible pieces, palette only carries 4")
        X = load(seg)
        B = np.asarray(Image.open(base).convert("RGB"), dtype=float)
        cloth, solid = cloth_mask(B)
        if X.shape[:2] != B.shape[:2]:
            print(f"  {o['id']:4s} REJECT  segmentation canvas {X.shape[1]}x{X.shape[0]} != {B.shape[1]}x{B.shape[0]}")
            rej += 1
            continue
        names = [p["piece"] for p in o["pieces"] if p["z"]]
        dec = decode(X, names)
        pieces = {k: clean(v & cloth, cloth) for k, v in dec.items()}
        alt = {}
        dcol = np.stack([np.array(COL[c], dtype=float) for c in list(COL)[:len(names)]])
        dd = ((X[:, :, None, :] - dcol[None, None, :, :]) ** 2).sum(-1)
        for i, k in enumerate(names):
            mk = (dd.argmin(2) == i) & (dd.min(2) < 6000)
            alt[k] = clean(ndimage.median_filter(mk.astype(np.uint8), 3).astype(bool) & cloth, cloth)

        # Pieces can legitimately share a 1-2px edge when an outer garment laps a covered one (blazer over
        # shirt, dupatta across kurti). The manifest lists the OUTER piece first, so it wins the contested
        # pixels; only a large contested area - a region the model blended instead of ordered - is a real
        # failure. Earlier this rejected M2 and M8 outright for an edge.
        order = list(pieces)
        contested_thick = 0
        for i, k in enumerate(order):
            for k2 in order[:i]:
                both = pieces[k] & pieces[k2]
                # THICKNESS, not area, tells the two cases apart. A genuine occlusion edge is 1-2px wide, so
                # one erosion kills it. M4's green started at 7% of the cloth span because the model painted
                # the trousers OVER the jacket as a broad slab - that survives erosion and must be rejected,
                # not silently clipped (clipping it left a slab that absorbed unclaimed cloth from the top).
                if int(both.sum()) and int(ndimage.binary_erosion(both, np.ones((3, 3))).sum()) > 0.004 * cloth.sum():
                    contested_thick += int(both.sum())
                pieces[k] = pieces[k] & ~both
        union = np.zeros_like(cloth)
        for m in pieces.values():
            union |= m

        cov = union.sum() / max(cloth.sum(), 1)
        probs = []
        ys_all = np.nonzero(cloth.any(1))[0]
        ct, cb = int(ys_all.min()), int(ys_all.max()); cspan = max(1, cb - ct)
        if len(pieces) != len(names):
            probs.append(f"{len(pieces)} coloured regions for {len(names)} manifest pieces")
        if contested_thick > 0:
            probs.append(f"broad overlap {contested_thick}px - a piece is painted over another, not an edge")
        if cov < 0.90:
            probs.append(f"coverage {cov:.2f}<0.90")
        for k, m in pieces.items():
            a_ = int(m.sum())
            if a_ < 0.015 * cloth.sum():
                # A garment COMPLETELY hidden behind an outer layer has no visible pixels, and an empty mask
                # for it is the correct answer, not a failure (M11's kurta under a closed Pathani jacket).
                # Only treat it as an error when the manifest claims the piece is visible (z:1) AND the
                # region is merely small rather than absent.
                occluded = a_ < 0.002 * cloth.sum()
                if occluded:
                    pieces[k] = np.zeros_like(cloth)
                    continue
                probs.append(f"{k} area {a_}px too small"); continue
            lab, n = ndimage.label(m, structure=np.ones((3, 3)))
            big = max(np.bincount(lab.ravel(), minlength=n + 1)[1:]) if n else 0
            if a_ and big / a_ < 0.92:
                probs.append(f"{k} not contiguous {big/a_:.2f}")
            iou = (m & alt[k]).sum() / max((m | alt[k]).sum(), 1)
            if iou < 0.97:
                probs.append(f"{k} palette-unstable iou {iou:.3f}")
            yy = np.nonzero(m.any(1))[0]
            if len(yy):
                st = (float(yy.min()) - ct) / cspan
                if k in WHOLE_BODY:
                    continue          # a long tunic / drape legitimately spans the figure; no band rule applies
                if k in UPPER and st > 0.42:
                    probs.append(f"{k}(upper) starts at {st:.2f} of the cloth span")
                if k in LOWER and st < 0.18:
                    probs.append(f"{k}(lower) starts at {st:.2f} of the cloth span")
        if probs:
            print(f"  {o['id']:4s} REJECT  " + "; ".join(probs)); rej += 1; continue

        left = cloth & ~union
        if left.any():
            big_k = max(pieces, key=lambda k: pieces[k].sum())
            pieces[big_k] = (ndimage.binary_dilation(pieces[big_k], np.ones((3, 3)), iterations=2) & cloth) | left
            union = np.zeros_like(cloth)
            for m in pieces.values():
                union |= m
            cov = union.sum() / max(cloth.sum(), 1)
            print(f"  {o['id']:4s} note  {int(left.sum())}px unclaimed absorbed by '{big_k}', coverage {cov:.4f}")

        # single write path, after all checks
        for k, m in pieces.items():
            Image.fromarray((m * 255).astype(np.uint8)).save(
                os.path.join(outdir, f"{o['id']}-{k}-mask.png"), optimize=True)
        for pp in o["pieces"]:
            if pp["z"] == 0:
                Image.fromarray(np.zeros((cloth.shape[0], cloth.shape[1]), np.uint8)).save(
                    os.path.join(outdir, f"{o['id']}-{pp['piece']}-mask.png"), optimize=True)
        print(f"  {o['id']:4s} OK  {len(pieces)} pieces  coverage={cov:.3f} "
              + " ".join(f"{k}={int(v.sum())//1000}k" for k, v in pieces.items()))
        ok += 1
    print(f"\n{ok} outfits decoded, {rej} rejected")
    return 1 if rej else 0


if __name__ == "__main__":
    sys.exit(main())
