"""Piece-level mask builder: split the garment into the pieces listed in template/pieces.json.

How the garment is found, and how its pieces are separated, without any neural net:

  cloth   = (inside the filled body silhouette) AND achromatic (saturation <= 12) AND brighter than the
            field in most of the frame. Skin is warm, the #808080 field is grey but OUTSIDE the silhouette,
            hair is dark. So cloth is determined by colour, not by pose -- which is exactly why one mask
            then serves all six tone files: skin L/S changes, cloth and background do not.
  seams   = horizontal bands of high edge energy INSIDE the cloth, at plausible y for that garment
            (a jacket hem, a sash, a dupatta edge). A blazer over a kurta shows as one bright band of
            gradient at the jacket hem line; the kurta continues below it.
  pieces  = the cloth region cut at its seams, top to bottom, labelled in the manifest's order.

This is a candidate generator with an enforced validator, not a black box: every mask is checked and a
garment whose seams cannot be resolved is reported as UNRESOLVED and needs a manual y override rather
than being shipped as a wrong mask. Manual overrides live in piece-overrides.json as
{ "<ID>": {"seams": [y1, y2, ...]} } in canvas pixels.

Usage (from repo root):
  python3 template/tools/make_masks.py                # build all + validate + write PNGs
  python3 template/tools/make_masks.py --only M2 W4   # subset
  python3 template/tools/make_masks.py --report       # print seam candidates for every outfit
Exit 1 if any piece fails validation.
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
from bgmask import body_silhouette

TW, TH = 768, 1376


UPPER = {"shirt", "blazer", "jacket", "nehru-jacket", "kurta-jacket", "polo", "top", "choli", "blouse",
         "kurti", "anarkali", "kurta", "sherwani", "waistcoat", "gown", "maxi", "midi", "kaftan", "jumpsuit"}
LOWER = {"trousers", "pants", "chinos", "jeans", "pajama", "churidar", "dhoti", "salwar", "palazzo",
         "sharara", "gharara", "lehenga", "skirt", "saree-drape", "draped-skirt"}
# role check: a piece named as upper-body must sit mostly above the cloth's mid-line, and vice versa.
# Without it the validator happily ships W1 with the "blouse" band under the drape and W4 with the "kurti"
# as a 35px collar sliver -- a partition that covers the cloth is NOT the same as a correct segmentation.


def head_void(X, solid):
    """The head is dark and near-achromatic, so it passes the achromatic test and used to be swallowed
    into the shirt mask (M1-shirt covered y=43). Hair sits in the top rows of the silhouette and is the
    darkest large blob there; everything at or above its bottom row is not cloth, whatever its colour."""
    L = X.mean(2)
    Hf, Wf = L.shape
    band = int(0.30 * Hf)
    dark = solid & (L < 104)
    dark[band:, :] = False
    if dark.sum() < 2000:
        return np.zeros_like(solid)
    lab, n = ndimage.label(dark, structure=np.ones((3, 3)))
    cs = np.bincount(lab.ravel(), minlength=n + 1)
    top = int(np.argmax(cs[1:])) + 1
    hair = lab == top
    ys, xs = np.nonzero(hair)
    void = np.zeros_like(solid)
    void[:int(ys.max()) + 12, max(0, xs.min() - 40):min(Wf, xs.max() + 40)] = True
    return void & solid


def cloth_mask(X):
    L, S = X.mean(2), X.max(2) - X.min(2)
    solid = ndimage.binary_fill_holes(body_silhouette(X))
    solid = solid & ~head_void(X, solid)
    achro = S <= 12
    bright = L > 150                                      # garment is #D5D5D5-ish, field is 128
    # grow brightness-seeded achromatic pixels so shaded folds join the piece instead of splitting it;
    # seeding on brightness (not on achromatic) is what keeps a dark trouser-shadow from becoming its own
    # piece and keeps the shoe block out, since footwear is neither bright nor warm.
    seed = solid & achro & bright
    grow = ndimage.binary_propagation(seed, mask=solid & achro & (L > 118))
    cloth = ndimage.binary_closing(grow, np.ones((5, 5)))
    lab, n = ndimage.label(cloth, structure=np.ones((3, 3)))
    if n > 1:
        cs = np.bincount(lab.ravel(), minlength=n + 1)
        cloth = np.isin(lab, [i for i in range(1, n + 1) if cs[i] > 4000])
    cloth = cloth & ndimage.binary_fill_holes(cloth) & solid
    return cloth, solid


def band_mask(cloth, y0, y1):
    """Rows of cloth between two cut lines, re-anchored on the piece's own widest row so a narrow
    sliver of unrelated cloth at the band edge (a collar point, a hem corner) cannot inherit the band."""
    b = np.zeros_like(cloth)
    b[max(0, y0):min(cloth.shape[0], y1), :] = True
    m = cloth & b
    m = ndimage.binary_closing(m, np.ones((5, 5)))
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    if n > 1:
        cs = np.bincount(lab.ravel(), minlength=n + 1)
        m = np.isin(lab, [int(np.argmax(cs[1:])) + 1])
    return ndimage.binary_fill_holes(m)


def seam_candidates(cloth, solid, n_pieces):
    """A seam is where the cloth gets NARROWER below it: a kurta hem, a jacket hem, a sash end. Rows where
    the garment keeps its width (a trouser thigh, a saree fall, a continuous A-line) are not boundaries no
    matter how much internal texture they carry -- that is what made the old detector put M6's seam at
    y=992 (inside the pajama) and W1's at y=1117 (near the ankles).

    Score(y) = 1 - widest cloth run below y / widest cloth run at or above y, so a real hem scores ~0.3-0.6
    and a mid-garment row scores near 0. Candidates are then greedily spread apart.
    """
    w = cloth.sum(1).astype(float)
    ys = np.nonzero(cloth.any(1))[0]
    if len(ys) < 60 or n_pieces < 2:
        return []
    y0, y1 = int(ys.min()), int(ys.max())
    span = max(1, y1 - y0)
    W = np.maximum(w, 1.0)
    above = np.array([W[y0:y + 1].max() for y in range(y0, y1 + 1)])
    below = np.array([W[y:y1 + 1].max() if y < y1 else 0.0 for y in range(y0, y1 + 1)])
    score = np.clip(1.0 - below / np.maximum(above, 1.0), 0, None)
    smooth = ndimage.gaussian_filter1d(score, 4)
    lo, hi = int(0.14 * span), int(0.90 * span)             # measured from the garment top, not the frame
    zone = np.zeros_like(smooth)
    zone[lo:hi] = smooth[lo:hi]
    out = []
    for y in np.argsort(zone)[::-1][: 400]:
        if any(abs(y - o) < int(0.11 * span) for o in out):
            continue
        if zone[y] < 0.05:
            break
        out.append(int(y))
        if len(out) == n_pieces - 1:
            break
    if len(out) < n_pieces - 1:                              # fill with edge-energy rows, as before
        edge = ndimage.gaussian_filter1d(np.abs(np.gradient(np.gradient(w))), 3)
        ez = np.where((np.arange(len(edge)) >= y0 + lo) & (np.arange(len(edge)) <= y0 + hi), edge, 0.0)
        for y in np.argsort(ez)[::-1][: 200]:
            if any(abs(int(y) - o) < int(0.11 * span) for o in out):
                continue
            out.append(int(y))
            if len(out) == n_pieces - 1:
                break
    return sorted(out)


def build_ids():
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    ov = {}
    p = os.path.join(ROOT, "template", "tools", "piece-overrides.json")
    if os.path.exists(p):
        ov = json.load(open(p))
    return man, ov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    man, ov = build_ids()
    outdir = os.path.join(ROOT, "template", "universal-masking")
    os.makedirs(outdir, exist_ok=True)
    ok = fail = skip = 0
    unresolved = []
    for o in man["outfits"]:
        if a.only and o["id"] not in a.only:
            continue
        src = os.path.join(ROOT, "template", o["image"])
        if not os.path.exists(src):
            skip += 1
            continue
        X = np.asarray(Image.open(src).convert("RGB"), dtype=float)
        cloth, solid = cloth_mask(X)
        names = [p["piece"] for p in o["pieces"] if p["z"]]
        if not names:
            names = [o["pieces"][0]["piece"]]
        seams = ov.get(o["id"], {}).get("seams") or seam_candidates(cloth, solid, max(2, len(names)))
        if a.report:
            print(f"  {o['id']:4s} {len(names)} piece(s) {names} seams={seams}")
            continue
        if len(names) >= 2 and len(seams) != len(names) - 1:
            unresolved.append((o["id"], len(names), seams)); fail += 1; continue
        ysc = np.nonzero(cloth.any(1))[0]
        top, bot = (int(ysc.min()), int(ysc.max())) if len(ysc) else (0, TH)
        span = max(1, bot - top)
        cuts = [top] + sorted(seams) + [bot + 1]
        bands = [band_mask(cloth, cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]
        if len(bands) == len(names):
            # The manifest lists pieces semantically (M2 = blazer, shirt, chinos); the bands are cut
            # top-to-bottom. Sort names by each band's centre row so a trouser band cannot inherit the
            # name of a garment that sits above it. Sort BOTH lists together, keeping them paired.
            cen = [float(np.nonzero(m.any(1))[0].mean()) if m.any() else 1e9 for m in bands]
            paired = sorted(zip(cen, bands, names), key=lambda t: t[0])
            bands = [b for _, b, _ in paired]
            names = [n for _, _, n in paired]
            o["pieces"] = [{"piece": n, "z": 1, "mask": f"universal-masking/{o['id']}-{n}-mask.png"}
                           for n in names] + [p for p in o["pieces"] if p["z"] == 0]

        # validation: pieces must not overlap, must lie inside cloth, must be non-trivial, union ~ cloth
        inter = np.zeros_like(cloth)
        union = np.zeros_like(cloth)
        for m in bands:
            if (m & inter).sum() > 0:
                fail += 1; unresolved.append((o["id"], "overlap", 0)); break
            inter |= m
            union |= m
        else:
            cover = union.sum() / max(cloth.sum(), 1)
            small = [names[i] for i, m in enumerate(bands) if m.sum() < max(3500, 0.07 * cloth.sum())]
            # a band whose area is a rounding error next to its neighbour is a mis-detected seam, not a
            # garment piece: that is how M13 shipped a 8.5k 'top' against a 302k 'trousers'.
            areas = [int(m.sum()) for m in bands]
            ratio = min(areas) / max(areas) if max(areas) else 0.0
            ordered = all(np.nonzero(band.any(0))[0].size for band in bands)
            skew = ""
            if len(areas) == 2 and ratio < 0.22:
                skew = f"piece-size-skew {ratio:.3f}"
            # Start-of-piece, not centre: an inner panel (M2 shirt, M4 waistcoat, M8 kurta) legitimately
            # hangs low under an open jacket, but it can never START below the chest. A "blouse" band
            # starting at 49% of the cloth span is a mislabelled drape, which is exactly what shipped
            # W1/W4 before this rule existed.
            roles = []
            for k, m in zip(names, bands):
                ysx = np.nonzero(m.any(1))[0]
                if not len(ysx):
                    continue
                st = (float(ysx.min()) - top) / span
                if k in UPPER and st > 0.42:
                    roles.append(f"{k}(upper) starts at {st:.2f} of the cloth span")
                if k in LOWER and st < 0.18:
                    roles.append(f"{k}(lower) starts at {st:.2f} of the cloth span")
            if roles:
                skew = "role-mismatch " + "; ".join(roles)
            if len(bands) != len(names) or small or cover < 0.86 or skew or not ordered:
                fail += 1
                unresolved.append((o["id"], f"cover={cover:.2f} small={small} {skew}", len(bands)))
                continue
            if not a.dry:
                for name, m in zip(names, bands):
                    Image.fromarray((m * 255).astype(np.uint8)).save(
                        os.path.join(outdir, f"{o['id']}-{name}-mask.png"), optimize=True)
            ok += 1
    if a.report:
        return 0
    print(f"masks: {ok} outfits written, {fail} rejected, {skip} bases not generated yet")
    for u in unresolved:
        print(f"  UNRESOLVED {u[0]}  {u[1]}  {u[2]}   -> needs template/tools/piece-overrides.json seam y-values")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
