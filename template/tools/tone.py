"""Re-tone skin on a frame to an exact luminance + saturation, and nothing else.

Why this exists: the generator renders Indian skin at saturation 61-83 on this flat-grey lighting, which
reads as a sprayed tan, and it also can NOT hit 6 discrete complexion steps from a text instruction alone.
Tone variants (and the base masters' own skin) are therefore produced by a measured colour transform on
the SAME pixels, which is also what keeps every frame pixel-locked so one universal mask fits all six.

Skin is found, not assumed: pixels inside the body silhouette that are warm (R>G>B), saturated and within
a luminance band around the frame's skin cluster; hair (dark), cloth (near-achromatic grey) and the
#808080 field are excluded by construction. The mask is then cleaned (largest components, small hole
fill, 1px feather) so the boundary lands on the real skin edge rather than a hard staircase.

Only L and S move. Hue is preserved (so the warm/cool character of the person stays), the garment and
background are never touched, and the edit is verified after the fact: changed pixels must lie inside the
skin mask, and the number of changed pixels outside it must be zero.

Usage:
  python3 template/tools/tone.py IN.jpg OUT.jpg --L 162 --S 40          # explicit targets
  python3 template/tools/tone.py IN.jpg OUT.jpg --tone light-tan        # from tone-ladder.json
  python3 template/tools/tone.py IN.jpg OUT.jpg --tone fair --report     # print before/after numbers
Exit 1 if the edit leaked outside the skin mask or the result is off-target by more than 4 L / 4 S.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bgmask import body_silhouette

LADDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tone-ladder.json")


def rgb_to_ls(X):
    """L = mean of channels, S = max-min (same definition the audit gate measures with)."""
    L = X.mean(2)
    S = X.max(2) - X.min(2)
    return L, S


def skin_mask(X, head_frac=0.45):
    """Warm, chromatic, non-grey pixels inside the body outline -- minus the hair void below the head.

    Two things this has to get right, both from real failures:
      * a light warm shoe sits in the same colour window as a hand, and got tinted. Hands are only
        admissible below the head if they are NOT inside the dark column the head casts (hair + the gap
        between chin and chest), so the head's hair void is carved out explicitly.
      * the neck has to be included up to the chin but must not spill into a collar opening: components
        are kept by size, and the closing step is small enough that a shirt placket is not bridged.
    """
    R, G, B = X[..., 0], X[..., 1], X[..., 2]
    L, S = rgb_to_ls(X)
    Hf, Wf = L.shape
    body = ndimage.binary_fill_holes(body_silhouette(X))
    warm = (R > G + 3) & (G >= B - 6) & (R > 40)
    cand = body & warm & (S > 10) & (L > 42) & (L < 236)
    lab, n = ndimage.label(cand, structure=np.ones((3, 3)))
    if n == 0:
        return cand
    cs = np.bincount(lab.ravel(), minlength=n + 1)
    keep = [i for i in range(1, n + 1) if cs[i] > 1200]
    m = np.isin(lab, keep) if keep else cand

    # locate the head: the kept component with the smallest top row. Its bbox bottom = chin line.
    tops = {i: int(np.nonzero(lab == i)[0].min()) for i in keep} or {1: 0}
    head_id = min(tops, key=lambda i: tops[i])
    hy, hx = np.nonzero(lab == head_id)
    chin, hleft, hright = int(hy.max()), int(hx.min()), int(hx.max())
    pad = int(0.14 * (hright - hleft))
    c0, c1 = max(0, hleft - pad), min(Wf, hright + pad)
    # hair void: the dark column between the crown and the chin line, inside the head's x-span
    crown = int(hy.min())
    col = slice(c0, c1)
    dark = (L < 96) & body
    void = np.zeros_like(m)
    seg = dark[max(0, crown - 60):chin + 2, col]
    void[max(0, crown - 60):chin + 2, col] = ndimage.binary_closing(seg, np.ones((9, 9)))
    m = m & ~void

    m = ndimage.binary_fill_holes(ndimage.binary_opening(m, np.ones((3, 3))))
    lab2, n2 = ndimage.label(m, structure=np.ones((3, 3)))
    hw = max(1, c1 - c0)
    keep2 = []
    for i in range(1, n2 + 1):
        yy, xx = np.nonzero(lab2 == i)
        if len(yy) < 900:
            continue
        top, bot = yy.min() / Hf, yy.max() / Hf
        wid = (xx.max() - xx.min()) / hw
        # hands on a straight-standing arm end at mid-thigh. Anything that starts below 72% of the
        # frame is footwear or hem, never a hand.
        if top > 0.72:
            continue
        # a bare-leg column under a skirt/saree hem: narrow, centred, and reaching the floor => not skin
        if bot > 0.95 and wid < 0.42 and abs(xx.mean() - (c0 + c1) / 2) < 0.55 * hw:
            continue
        keep2.append(i)
    m = np.isin(lab2, keep2) if keep2 else m & False
    return m


def feather(m, sigma=0.8):
    return np.clip(ndimage.gaussian_filter(m.astype(float), sigma) * 1.0, 0, 1)


def apply_tone(src, dst, Lt, St, report=False):
    im = Image.open(src).convert("RGB")
    X = np.asarray(im, dtype=float)
    L, S = rgb_to_ls(X)
    m = skin_mask(X)
    if m.sum() < 8000:
        print(f"FAIL: skin cluster only {int(m.sum())} px -- refusing to guess")
        return 1
    w = feather(m)
    sL = float(L[m].mean())
    sS = float(S[m].mean())
    dL, dS = Lt - sL, St - sS
    Y = X.copy()
    # move luminance, then equalise chroma to the target, keeping hue (ratios of the channels' offsets)
    for c in range(3):
        off = X[..., c] - L
        gain = (St / max(sS, 1e-6)) if sS > 6 else 1.0
        Y[..., c] = Y[..., c] + dL + off * (gain - 1.0)
    Y = np.clip(Y, 0, 255)
    Z = X * (1 - w[..., None]) + Y * w[..., None]
    Z = np.clip(Z, 0, 255).astype(np.uint8)
    Image.fromarray(Z).save(dst, quality=95, subsampling=0, optimize=False)

    nL, nS = rgb_to_ls(Z.astype(float))
    aL, aS = float(nL[m].mean()), float(nS[m].mean())
    # leakage: pixels outside the (dilated) skin mask that moved at all
    hard = ndimage.binary_dilation(m, np.ones((3, 3)), iterations=2)
    moved = (np.abs(Z.astype(float) - X).max(2) > 2)
    leak = int((moved & ~hard).sum())
    tot = int(moved.sum())
    ok = (abs(aL - Lt) <= 4.0) and (abs(aS - St) <= 4.0) and leak == 0
    if report or not ok:
        print(f"  skin px={int(m.sum()):7d} moved={tot:7d} L {sL:6.1f}->{aL:6.1f} (want {Lt:5.1f}) "
              f"S {sS:5.1f}->{aS:5.1f} (want {St:4.1f})  leak={leak}px  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--L", type=float, default=None)
    ap.add_argument("--S", type=float, default=None)
    ap.add_argument("--tone", default="")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    Lt, St = a.L, a.S
    if a.tone:
        lad = json.load(open(LADDER))["tones"][a.tone]
        Lt, St = lad["skinL"], lad["skinS"]
    if Lt is None or St is None:
        print("need --L/--S or a --tone present in tone-ladder.json")
        return 2
    return apply_tone(a.src, a.dst, Lt, St, a.report)


if __name__ == "__main__":
    sys.exit(main())
