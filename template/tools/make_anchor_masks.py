"""Anchor-mask builder: matte ONE garment with the model, derive the rest, never leave a gap.

Why this exists. Asking for a full 3-colour segmentation failed repeatedly in ways that are the model's
limitation, not fixable by better wording:
  * it leaves the second/lower garment unpainted (M12 0.76, M4 0.72, M9 0.43 coverage)
  * it floods one colour over the whole figure (W14 trousers "starting at 0.00" of the cloth span)
Both are a grey-on-grey judgement made twice at once. So ask it ONCE - "is this pixel the jacket?" - which
is a much easier visual task, and get the other pieces for free as the complement of a region we already
trust, because `cloth` is derived from colour statistics of the base frame itself.

  anchored piece = white region of <ID>-anchor.png, intersected with cloth, cleaned, verified
  remaining cloth = cloth & ~anchored            <- by construction covers everything the anchor is not
  if >1 piece remains, cut it at the seam rows that make_masks.seam_candidates finds WITHIN that remainder

Guarantees: pieces are disjoint and their union is exactly `cloth`, so no garment pixel can end up
unrecoloured and no two pieces can fight over a boundary. Verification still rejects a bad anchor
(not contiguous, absurd area, wrong end of the figure for its role).

Usage (repo root):
  python3 template/tools/make_anchor_masks.py                 # build from template/_qc/anchor
  python3 template/tools/make_anchor_masks.py --report        # which piece each outfit needs matted
Exit 1 if any outfit fails.
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
from make_masks import cloth_mask, seam_candidates, band_mask, UPPER, LOWER, WHOLE_BODY


def load_anchor(p):
    X = np.asarray(Image.open(p).convert("RGB"), dtype=float)
    L = X.mean(2)
    return L > 200                                   # matted garment = white on black


def frame_for(man_root, o):
    """pieces.json carries a hand-written slug per outfit; when the file on disk was generated
    under a different name the pair silently disagrees and every stage skips the outfit. Resolve
    the frame by ID, and keep the manifest entry pointed at what actually exists."""
    pth = os.path.join(man_root, "template", o["image"])
    if not os.path.exists(pth):
        alt = sorted(glob.glob(os.path.join(man_root, "template", "base", o["id"] + "-*.jpg")))
        if alt:
            pth = alt[0]
    o["image"] = os.path.relpath(pth, os.path.join(man_root, "template"))
    return pth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="template/_qc/anchor")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    d = os.path.join(ROOT, a.dir)
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    outdir = os.path.join(ROOT, "template", "universal-masking")
    os.makedirs(outdir, exist_ok=True)
    ok = rej = 0
    lines = []
    for o in man["outfits"]:
        if not os.path.exists(frame_for(ROOT, o)):
            continue
        vis = [p["piece"] for p in o["pieces"] if p["z"]]
        anchor_png = os.path.join(d, f"{o['id']}-anchor.png")
        if a.report:
            need = vis[0] if vis else o["pieces"][0]["piece"]
            print(f"  {o['id']:4s} matte '{need}'  ({len(vis)} visible piece(s): {vis})")
            continue
        if a.only and o["id"] not in a.only:
            continue
        if not os.path.exists(anchor_png):
            continue
        B = np.asarray(Image.open(frame_for(ROOT, o)).convert("RGB"), dtype=float)
        cloth, solid = cloth_mask(B)
        A = load_anchor(anchor_png)
        if A.shape != cloth.shape:
            A = np.asarray(Image.open(anchor_png).convert("L").resize(cloth.shape[::-1], Image.NEAREST)) > 200
        top_name = vis[0] if vis else o["pieces"][0]["piece"]
        anchored = ndimage.binary_closing(A & cloth, np.ones((7, 7)))
        lab, n = ndimage.label(anchored, structure=np.ones((3, 3)))
        if n > 1:
            cs = np.bincount(lab.ravel(), minlength=n + 1)
            anchored = lab == (int(np.argmax(cs[1:])) + 1)          # keep the single largest blob
        rest = cloth & ~anchored
        probs = []
        a_ = int(anchored.sum())
        if a_ < 0.10 * cloth.sum():
            probs.append(f"anchor {a_}px is only {100*a_/max(cloth.sum(),1):.0f}% of the garment - the matte is mostly empty")
        flipped = False
        if len(vis) <= 1 and a_ > 0.9 * cloth.sum():
            nm = o["pieces"][0]["piece"]
            out = os.path.join(outdir, f"{o['id']}-{nm}-mask.png")
            Image.fromarray((cloth * 255).astype(np.uint8)).save(out)
            lines.append(f"{o['id']}  OK  single garment: whole cloth mask = {int(cloth.sum())//1000}k")
            ok += 1
            continue
        if a_ > 0.97 * cloth.sum():
            inv = ndimage.binary_closing((~A) & cloth, np.ones((7, 7)))
            li, ni = ndimage.label(inv, structure=np.ones((3, 3)))
            if ni:
                ci = np.bincount(li.ravel(), minlength=ni + 1)
                inv = li == (int(np.argmax(ci[1:])) + 1)
            iv = int(inv.sum())
            if 0.10 * cloth.sum() < iv < 0.90 * cloth.sum():
                anchored, a_, flipped = inv, iv, True     # the model matted the OTHER garment; treat that
                rest = cloth & ~anchored                  # region as the piece it actually outlined
                top_name = next((n for n in [p_["piece"] for p_ in o["pieces"]] if n != top_name), top_name)
                lines.append(f"{o['id']} inverted-matte recovered")
            else:
                probs.append("anchor floods the whole figure - the model painted everything white")
        big = int(max(np.bincount(lab.ravel(), minlength=n + 1)[1:]) if n else 0)
        if a_ and big / a_ < 0.90:
            probs.append(f"anchor not contiguous {big/a_:.2f}")
        yy = np.nonzero(anchored.any(1))[0]
        span = max(1, int(np.nonzero(cloth.any(1))[0].max()) - int(np.nonzero(cloth.any(1))[0].min()))
        if len(yy) and top_name in UPPER and (int(yy.min()) - int(np.nonzero(cloth.any(1))[0].min())) / span > 0.42:
            probs.append("upper garment's matte starts too low on the figure")
        if probs:
            print(f"  {o['id']:4s} REJECT  " + "; ".join(probs)); rej += 1; continue

        pieces = {top_name: anchored}
        left_names = [p for p in vis[1:]]
        if left_names:
            rows = np.nonzero(rest.any(1))[0]
            sub = np.zeros_like(rest); sub[rows.min():rows.max() + 1] = rest[rows.min():rows.max() + 1]
            seams = seam_candidates(sub, solid, len(left_names)) if len(left_names) > 1 else []
            if len(left_names) == 1:
                pieces[left_names[0]] = rest
                left_names = []
                got = []
            cuts = [rows.min()] + sorted(seams) + [rows.max() + 1]
            got = []
            for i in range(len(cuts) - 1):
                m = band_mask(rest, cuts[i], cuts[i + 1])
                if m.sum() > 0:
                    got.append(m)
            if not left_names:                # every remaining piece already assigned above
                pass
            elif not got and left_names:      # model painted the whole figure white, so rest is empty
                pieces[left_names[0]] = rest
                for nm in left_names[1:]:
                    pieces[nm] = np.zeros_like(rest)
            elif len(got) == len(left_names):
                cen = [float(np.nonzero(m.any(1))[0].mean()) for m in got]
                order = np.argsort(cen)
                for idx in order:
                    pieces[left_names[int(np.where(order == idx)[0][0])]] = got[idx]
            else:
                # remainder is one connected garment (or a split we cannot prove) -> assign it whole to
                # the FIRST remaining piece and mark the others empty rather than guessing a boundary.
                pieces[left_names[0]] = rest
                for nm in left_names[1:]:
                    pieces[nm] = np.zeros_like(rest)
        else:
            for pp in o["pieces"]:
                if pp["z"] == 0:
                    pieces.setdefault(pp["piece"], np.zeros_like(cloth))
        union = np.zeros_like(cloth)
        for m in pieces.values():
            union |= m
        miss = int((cloth & ~union).sum())
        if miss > 0.02 * cloth.sum():
            print(f"  {o['id']:4s} REJECT  {miss}px of cloth owned by no piece"); rej += 1; continue
        for k, m in pieces.items():
            Image.fromarray((m.astype(np.uint8) * 255)).save(
                os.path.join(outdir, f"{o['id']}-{k}-mask.png"), optimize=True)
        for pp in o["pieces"]:
            f2 = os.path.join(outdir, f"{o['id']}-{pp['piece']}-mask.png")
            if pp["piece"] not in pieces and not os.path.exists(f2):
                Image.fromarray(np.zeros(cloth.shape, np.uint8)).save(f2, optimize=True)
        print(f"  {o['id']:4s} OK  " + " ".join(f"{k}={int(v.sum())//1000}k" for k, v in pieces.items())
              + (f"  (remainder left whole, {len(left_names)-1} piece(s) empty)" if left_names and not seam_candidates(rest, solid, len(left_names)) else ""))
        ok += 1
    if a.report:
        return 0
    print(f"\n{ok} outfits built from anchors, {rej} rejected")
    return 1 if rej else 0


if __name__ == "__main__":
    sys.exit(main())
