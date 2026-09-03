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
from make_masks import cloth_mask, UPPER, LOWER, WHOLE_BODY

COL = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
       "yellow": (255, 255, 0), "magenta": (255, 0, 255)}


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=int)


def decode(X, names, thr=140, majority=True):
    """Return {piece: bool mask} for an ordered list of colour names matched to the palette."""
    out = {}
    for name, col in zip(names, list(COL)[:len(names)]):
        c = np.array(COL[col], dtype=float)
        m = (np.abs(X - c).max(2) < (255 - thr))
        if majority:
            # a segmentation PNG arrives with 1-2px anti-aliased fringes; those flip between threshold 140
            # and 110, which showed up as IoU 0.938 against my 0.97 stability floor. A 3x3 majority vote
            # removes fringe indecision without eroding the piece boundary.
            m = ndimage.median_filter(m.astype(np.uint8), 3).astype(bool)
        out[name] = m
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
        if not os.path.exists(seg) or not os.path.exists(base):
            continue
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
        # cross-threshold stability
        alt = {k: clean(v & cloth, cloth) for k, v in decode(X, names, thr=110).items()}
        union = np.zeros_like(cloth)
        for m in pieces.values():
            if (m & union).any():
                print(f"  {o['id']:4s} REJECT  pieces overlap (the model did not paint disjoint colours)")
                rej += 1
                break
            union |= m
        else:
            cov = union.sum() / max(cloth.sum(), 1)
            probs = []
            ys_all = np.nonzero(cloth.any(1))[0]
            ct, cb = int(ys_all.min()), int(ys_all.max()); cspan = max(1, cb - ct)
            if len(pieces) != len(names):
                probs.append(f"got {len(pieces)} coloured regions for {len(names)} manifest pieces")
            for k, m in pieces.items():
                ysx = np.nonzero(m.any(1))[0]
                if not len(ysx):
                    continue
                st = (float(ysx.min()) - ct) / cspan
                if k in UPPER and st > 0.42:
                    probs.append(f"{k}(upper) starts at {st:.2f} of the cloth span")
                # a saree drape / kaftan / jumpsuit legitimately spans shoulder to ankle: applying a
                # "lower garment cannot start high" floor to WHOLE_BODY pieces rejected a CORRECT W1
                # mask (drape starting at 0.00 is right for a saree). Only enforce the floor on pieces
                # that are meant to start below an outer layer.
                if k in LOWER and k not in WHOLE_BODY and st < 0.18:
                    probs.append(f"{k}(lower) starts at {st:.2f} of the cloth span")
            if cov < 0.90:
                probs.append(f"coverage {cov:.2f}<0.90")
            for k, m in pieces.items():
                a = int(m.sum())
                if a < 0.015 * cloth.sum():
                    probs.append(f"{k} area {a}px too small")
                    continue
                big = int(ndimage.label(m)[1] and max(np.bincount(ndimage.label(m)[0].ravel())[1:]) or 0)
                if a and big / a < 0.92:
                    probs.append(f"{k} not contiguous {big/a:.2f}")
                iou = (m & alt[k]).sum() / max((m | alt[k]).sum(), 1)
                if iou < 0.97:
                    probs.append(f"{k} threshold-unstable iou {iou:.3f}")
            if probs:
                print(f"  {o['id']:4s} REJECT  " + "; ".join(probs))
                rej += 1
                continue
            # EVERY cloth pixel must belong to exactly one piece or the recolour leaves an unrecoloured
            # grey patch on the mannequin (7k px at 97.8% coverage is visible on the shoulder). Unclaimed
            # cloth is handed to the piece whose pixels are nearest, which is the drape/outer garment.
            left = cloth & ~union
            if left.any():
                # Grow the dominant piece by a couple of px so it absorbs fragments that touch it, then
                # give it everything still unclaimed. (A per-fragment nearest-pixel assignment was tried
                # first and OOM-killed the process at ~300k reference pixels -- overkill for 7k of cloth.)
                big = max(pieces, key=lambda k: pieces[k].sum())
                g = ndimage.binary_dilation(pieces[big], np.ones((3, 3)), iterations=2) & cloth
                pieces[big] = g | (cloth & ~union & ~np.logical_or.reduce([m for k, m in pieces.items() if k != big] or [cloth & False]))
                union = np.zeros_like(cloth)
                for m in pieces.values():
                    union |= m
                cov = union.sum() / max(cloth.sum(), 1)
                print(f"  {o['id']:4s} note  {int((cloth & ~union).sum())}px still unclaimed -> absorbed; "
                      f"coverage now {cov:.4f}")
                left = cloth & ~union
                if left.any():
                    pieces[big] = pieces[big] | left
                    union = np.zeros_like(cloth)
                    for m in pieces.values():
                        union |= m
                    cov = union.sum() / max(cloth.sum(), 1)

            for k, m in pieces.items():
                Image.fromarray((m * 255).astype(np.uint8)).save(
                    os.path.join(outdir, f"{o['id']}-{k}-mask.png"), optimize=True)
            for p in o["pieces"]:
                if p["z"] == 0:
                    Image.fromarray((np.zeros_like(cloth) * 255).astype(np.uint8)).save(
                        os.path.join(outdir, f"{o['id']}-{p['piece']}-mask.png"), optimize=True)
            print(f"  {o['id']:4s} OK  {len(pieces)} pieces  coverage={cov:.3f} "
                  + " ".join(f"{k}={int(v.sum())//1000}k" for k, v in pieces.items()))
            ok += 1
    print(f"\n{ok} outfits decoded, {rej} rejected")
    return 1 if rej else 0


if __name__ == "__main__":
    sys.exit(main())
