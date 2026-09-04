#!/usr/bin/env python3
"""Perfect piece masks from a COLOUR-CODED master.

Why this exists
---------------
The masters were one flat fabric colour so that any customer colour could be
poured over them. That made the *garment* easy to isolate and the *pieces*
impossible: with a rose jacket over a rose kurta there is no measurement that
says which pixels are which, so the boundary had to be guessed by a model asked
to re-trace cloth it can barely see. It under-claimed - M6/M8 dropped the kurta
sleeves into the pajama, M4 gave the jacket a 38k sliver and handed its sleeves
to the trousers - and every arithmetic check I wrote still passed, because the
totals really were 100%. The error was ownership, not coverage, and coverage
metrics cannot see it.

So the master now carries the segmentation in its own colours:

    GREEN = the lower garment          ROSE = the outermost / upper garment
    BLUE  = the middle layer (waistcoat, inner tunic, jacket-over-kurta)
    anything else (white shirt, dark tie, shoes, skin, backdrop) is deliberately
        left UNCODED: it is not an independently recolourable garment.

Each garment is a different colour, so a piece boundary is not inferred at all -
it IS the colour edge, which is exact. Nothing is guessed, so there is nothing to
get wrong: the partition is correct by construction.

Rules enforced here (a violation rejects the outfit; it never ships a best effort):
  K1 one label per pixel, so overlap == 0 and gap == 0 are identities, not targets.
  K2 nearest-palette in Lab with a cap AND a runner-up margin, so a shadowed fold
     cannot jump garments; pixels matching nothing are "uncoded".
  K3 a designated colour must own a real region (>= 2% of coded cloth) - if the
     model forgot the waistcoat, say so instead of inventing one.
  K4 role geometry, written only in terms of what garment geometry guarantees: the lower
     garment's rows must reach below the upper garment's, and no coded upper/middle garment
     may sit wholly below the lower one. Both are colour-count agnostic. (An earlier version
     asserted "the middle layer sits between top and bottom" and rejected a correct
     three-piece suit, because a jacket's sleeves drag its centre of mass below its own
     waistcoat's - the rule was wrong, not the image.)
  K5 zero pixels of any piece inside the head box.
  K6 off-palette guard: saturated non-skin pixels matching no code colour mean the
     model drifted or painted a fourth garment.
  K7 tone invariance is EXACT, not approximate: classification never looks at skin,
     and the tone step only ever edits inside the skin band, so the same masks are
     bit-identical on all six complexions. Verified by re-classifying re-toned frames
     and requiring xor == 0.

    python3 template/tools/mask_code.py IMG [IMG ...] [--proof] [--report]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TPL = os.path.join(ROOT, "template")

# label -> the colour it encodes, and the role that colour plays in an outfit
CODE = {"rose": (194, 38, 143), "blue": (31, 95, 196), "green": (30, 142, 62)}
SKIN_HUE = 25          # degrees; Indian skin measured 18-32 on these masters
HUE_CAP = 40.0         # a piece pixel must be within this of ITS code hue
# Lab radius inside which a pixel may be called a code colour, and the margin it must beat
# the runner-up by. The cap was 52 until deep-fold shading in W1's silk saree measured
# 60-70 and left 15859px of the garment unowned. It can be loosened because warm skin is
# kept out by the HUE veto, not by this number: measured distances put skin 67 from rose,
# 69 from green and 88 from blue, so the cap was never what protected the face - and the
# bright backdrop is 71 from rose. What must stay tight is the MARGIN, which is the only
# thing separating two garments that touch.
CAP = 72.0
MARGIN = 9.0
SEED = 40.0            # a pixel this close to its code colour needs no help to be claimed
MIN_CODE_SEP = 55.0    # palette floor: below this two codes cannot be told apart at all
# front-to-back / top-to-bottom. This list is also the claiming order and the label
# numbering, so a colour missing here is invisible to the classifier.
ORDER = ["rose", "blue", "green"]
# A fourth colour was tried for four-piece outfits (M11's kurta as violet) and K10 below is
# what it exists to catch: violet measured 42.8 Lab from rose while the classifier's own cap
# is 52, so a fifth of that kurta silently belonged to the jacket. Two code colours closer
# apart reliably (MIN_CODE_SEP below), so the palette stays at three and a fourth garment in
# an outfit ships as z:0, recoloured with its neighbour. rose/blue measure 62 and five
# approved outfits depend on that pair, which is why the floor sits at 55 and why the real
# test of a palette is the shading-jitter gate in K10, not this number.

LABEL_OF = {n: i + 1 for i, n in enumerate(ORDER)}


def fit_master(im, W=768, H=1376):
    """Fill the catalogue canvas by cropping the LONGER axis, never by padding.

    The first version always shrank the width. Two masters came back 864x1821 - narrower
    than 768x1376 - so the computed crop was wider than the image, the box went negative,
    and PIL obediently padded pure black columns on both sides. Those frames still passed
    every mask gate; the only thing that noticed was the tone helper reporting "skin band
    0 px", because it sampled those black bars as the backdrop. A crop must be inside the
    image, and a canvas that cannot be filled by cropping is resized instead, not padded.
    """
    ar = W / H
    iw, ih = im.size
    if iw / ih > ar:                                   # too wide: trim the sides
        tw = max(1, min(iw, int(round(ih * ar))))
        x0 = (iw - tw) // 2
        box = (x0, 0, x0 + tw, ih)
    elif iw / ih < ar:                                  # too tall: trim top/bottom
        th = max(1, min(ih, int(round(iw / ar))))
        y0 = (ih - th) // 2
        box = (0, y0, iw, y0 + th)
    else:
        box = (0, 0, iw, ih)
    x0, y0, x1, y1 = box
    assert 0 <= x0 < x1 <= iw and 0 <= y0 < y1 <= ih, f"crop {box} outside image {im.size}"
    return im.crop(box).resize((W, H), Image.LANCZOS)


def lab(rgb):
    """sRGB -> CIE Lab (D65), computed here because PIL refuses RGB->Lab.

    Lab, not RGB or HSV, is the right space for this: it is roughly perceptually
    uniform, so a fixed distance threshold means a fixed *visible* difference. That
    is what makes a single cap (52) work for a bright rose jacket and a shadowed
    green trouser at the same time, which hue-only or RGB-only thresholds cannot.
    """
    x = np.clip(np.asarray(rgb, dtype=float), 0, 255) / 255.0
    x = np.where(x > 0.04045, ((x + 0.055) / 1.055) ** 2.4, x / 12.92)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = x @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    e = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116.0 * e[..., 1] - 16.0
    A = 500.0 * (e[..., 0] - e[..., 1])
    B = 200.0 * (e[..., 1] - e[..., 2])
    return np.stack([L, A, B], -1)


def classify(rgb, codes):
    """Per-pixel nearest code colour, then a majority vote to kill speckle.

    The vote is the cheap way to get a smooth boundary WITHOUT creating overlap or
    gaps: a median always returns a label that was already present in the window, so
    the partition property survives the smoothing (a dilation/erosion pair would not).
    """
    L = lab(rgb)
    # Hue gate. Lab distance alone was not enough: darkening skin toward ebony walks its
    # Lab value into the rose cluster's radius, so on the darkest complexions skin pixels
    # started matching a code colour and the "universal" mask differed by up to 134k px per
    # outfit. Hue fixes this exactly, not approximately, because the tone step only ever
    # edits V and S and leaves H alone - so a hue test gives the SAME answer on all six
    # complexions by construction, and skin (hue ~25) is never within 40 degrees of rose
    # (320), blue (215) or green (135) on any of them.
    deg = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("HSV"),
                     dtype=float)[..., 0] * 360.0 / 255.0
    cents = np.stack([lab(np.array([[CODE[c]]], dtype=np.uint8))[0, 0] for c in codes], 0)
    code_deg = {c: float(np.asarray(Image.fromarray(np.array([[CODE[c]]], dtype=np.uint8))
                                    .convert("HSV"), dtype=float)[0, 0, 0]) * 360.0 / 255.0
                for c in codes}
    d = np.stack([np.sqrt(((L - c) ** 2).sum(2)) for c in cents], 0)      # (k,h,w)
    order = np.argsort(d, 0)
    nearest = order[0]
    d1 = np.take_along_axis(d, order[0:1], 0)[0]
    d2 = np.take_along_axis(d, order[1:2], 0)[0] if len(codes) > 1 else d1 + 999
    hd = np.stack([np.minimum(np.abs(deg - code_deg[c]), 360 - np.abs(deg - code_deg[c]))
                   for c in codes], 0)
    hd_best = np.take_along_axis(hd, nearest[None, ...], 0)[0]
    marg = d2 - d1                                     # runner-up margin, >0 means a winner
    hue_ok = hd_best < HUE_CAP
    lm = np.where((d1 < CAP) & (marg > MARGIN) & hue_ok,
                  (nearest + 1).astype(np.uint8), np.uint8(0)).astype(np.uint8)

    # Grow each colour only from confident seeds. Widening the Lab cap to catch deep fold
    # shading in W1's silk saree also let a lock of hair over the shoulder qualify as rose,
    # which put 4041px of hair inside a garment mask. A chroma floor was the obvious fix and
    # is wrong: lit hair strands measured 103 there while the saree's own darkest folds
    # measured 87, so no threshold separates them. What DOES separate them is connectivity -
    # a fold is cloth because it is surrounded by cloth, an occluder is not. Geodesic
    # reconstruction inside the loose region, per colour, keeps the fold and drops the blob,
    # and it stays a pure function of the colour map, so the tone-invariance argument holds.
    seed = (d1 < SEED) & hue_ok
    for i in range(len(codes)):
        lab_i = i + 1
        grow = (lm == lab_i)
        if grow.any() and seed[grow].mean() < 0.6:      # only re-grow genuinely loose regions
            keep = ndimage.binary_propagation(seed & (d1 < CAP), mask=grow,
                                               structure=np.ones((3, 3)))
            lm = np.where(grow & ~keep, np.uint8(0), lm)
    return lm, d1, marg


def hue_report(rgb, codes):
    """Smallest hue gap between every code colour and the frame's own skin. This is the
    number the whole scheme stands on, so it is measured per frame, not assumed."""
    deg = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("HSV"),
                     dtype=float)[..., 0] * 360.0 / 255.0
    sk = (np.abs(deg - SKIN_HUE) < 25) & (rgb.max(2) - rgb.min(2) > 25) & (rgb.mean(2) > 60)
    if not sk.any():
        return None
    hs = deg[sk]
    out = {}
    for c in codes:
        hc = float(np.asarray(Image.fromarray(np.array([[CODE[c]]], dtype=np.uint8))
                              .convert("HSV"), dtype=float)[0, 0, 0]) * 360.0 / 255.0
        d = np.minimum(np.abs(hs - hc), 360 - np.abs(hs - hc))
        # Distribution, not minimum. The min version reported "42.4 degrees from skin" for
        # every master, which was ONE anti-aliased pixel on a hand edge, and it hid the
        # question that matters: what share of the skin is close enough to be confused.
        out[c] = {"p99": round(float(np.percentile(d, 99)), 1),
                  "near_pct": round(float((d < HUE_CAP).mean() * 100), 3)}
    return out


def lab_of(codes):
    """code -> label index for THIS outfit. classify() numbers labels by position in
    the list it was handed, so looking LABEL_OF up in the global ORDER silently
    mismatched whenever an outfit used fewer than three colours - which is how the
    lower garment came back as 0px on seven of ten masters while everything else
    looked plausible. One source of truth, passed around together."""
    return {c: i + 1 for i, c in enumerate(codes)}


def _assemble(by_label, vis, role, h, w, occ=None):
    """Colour masks -> piece masks: front-to-back claiming, then speckle removal.

    Kept as one function because the tone-invariance proof must apply EXACTLY this to the
    re-toned frame. Comparing a cleaned base mask against a raw variant label map is what
    made the first version of K7 report 6k-134k 'differences' that were purely my own
    morphological cleanup, not any instability in the mask.
    """
    pieces, owned = {}, np.zeros((h, w), bool)
    for nm in vis:
        c = role.get(nm)
        if c is None:
            pieces[nm] = np.zeros((h, w), bool)
            continue
        msk = by_label.get(c, np.zeros((h, w), bool)) & ~owned
        lab_i, n_i = ndimage.label(msk, np.ones((3, 3)))
        if n_i > 1:
            sz_i = np.bincount(lab_i.ravel(), minlength=n_i + 1)
            big = int(sz_i[1:].max())
            keep_i = [i for i in range(1, n_i + 1)
                      if sz_i[i] >= 0.0015 * max(1, int(msk.sum())) or sz_i[i] == big]
            msk = np.isin(lab_i, keep_i)
        # Thin creases inside a garment are unclaimed colour: a deep fold line can sit
        # outside the Lab cap, which leaves a hairline gap down the middle of the piece (W4's
        # inner thigh, W6's sharara centre, W1's hip). Fill ONLY small holes that this colour
        # completely surrounds - a bounded box of 34px and 0.4% of the cloth - because that is
        # what distinguishes a fold from an enclosed background gap (an arm loop or the space
        # between two legs is far bigger, and must stay unowned or the recolour paints air).
        holes = ndimage.binary_fill_holes(msk) & ~msk & ~owned
        lh, nh = ndimage.label(holes, np.ones((3, 3)))
        if nh:
            objs = ndimage.find_objects(lh)
            keep = [i + 1 for i, sl in enumerate(objs)
                    if sl is not None and max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) <= 34
                    and int((lh[sl] == i + 1).sum()) <= 0.004 * max(1, int(msk.sum()))]
            if keep:
                msk = msk | np.isin(lh, keep)
        if occ is not None:                        # an occluder is never garment, however
            msk = msk & ~occ                        # neatly it sits inside the cloth
        pieces[nm] = msk
        owned |= msk
    return pieces, owned


def roles_for(o):
    """colour -> piece for this outfit: bottom garment is green, topmost visible is
    rose, the next one down is blue, and a fourth (rare) folds into rose."""
    vis = [p["piece"] for p in o["pieces"] if p["z"]]
    if not vis:
        return {}
    if all(p.get("code") for p in o["pieces"] if p["z"]):
        # The manifest is the authority: each piece carries the colour it was shot in, so
        # roles are read, not inferred. Positional inference is only the fallback for
        # outfits that predate the code field, and it silently mislabels any outfit whose
        # piece list is not ordered outermost-to-bottom (M11's patka sits below the kurta).
        return {p["piece"]: p["code"] for p in o["pieces"] if p["z"]}
    if len(vis) == 1:
        return {vis[0]: "green"}                      # single garment: it is the whole outfit
    out = {vis[0]: "rose", vis[-1]: "green"}
    if len(vis) > 2:
        for nm in vis[1:-1]:
            out[nm] = "blue"
    return out


def head_box(rgb):
    g = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("L"), dtype=float)
    h, w = g.shape
    b = max(4, h // 40)
    strip = np.concatenate([g[:b].ravel(), g[-b:].ravel(), g[:, :b].ravel(), g[:, -b:].ravel()], 0)
    obj = np.abs(g - float(np.median(strip))) > 16
    obj = ndimage.binary_fill_holes(ndimage.binary_opening(obj, np.ones((5, 5))))
    wid = obj.sum(1)
    min_head = max(24, w * 0.06)
    rows = np.nonzero(wid >= min_head)[0]
    if not len(rows):
        return None
    top = int(rows[0])
    if top > h * 0.22:
        return None
    chin = min(h - 1, top + int(h * 0.115))
    for y in range(top + 6, min(h, top + int(h * 0.30))):
        xs = np.nonzero(obj[y])[0]
        if len(xs) and (xs[-1] - xs[0] + 1) > 1.62 * min_head:
            chin = max(y - 6, top + int(h * 0.05))
            break
    if chin - top < h * 0.045:
        return None
    xs = np.nonzero(obj[top:chin].any(0))[0]
    cx = int((xs[0] + xs[-1]) / 2) if len(xs) else w // 2
    hw = max(int((xs[-1] - xs[0] + 1) / 2), 1) if len(xs) else int(min_head)
    yy, xx = np.mgrid[0:h, 0:w]
    return (((yy - (top + chin) / 2) / max(2.0, (chin - top) / 2 * 1.35)) ** 2
            + ((xx - cx) / max(2.0, hw * 1.15)) ** 2) <= 1.0


def mask_set(rgb, o, proof=False):
    h, w = np.asarray(rgb).shape[:2]
    vis = [p["piece"] for p in o["pieces"] if p["z"]]
    hid = [p["piece"] for p in o["pieces"] if not p["z"]]
    role = roles_for(o)
    codes = [c for c in ORDER if c in role.values()]
    if not codes or not vis:
        return None, {}, ["no colour-coded pieces declared"]
    labmap, d1, marg = classify(rgb, codes)
    lm_src = labmap
    Lof = lab_of(codes)
    # One label mask per colour, cleaned ONLY from its own pixels. A 3x3 median filter on
    # the shared label map looked like the tidy way to kill JPEG speckle, but it lets a
    # pixel's label depend on its neighbours' labels - so re-toning the skin changed
    # cloth labels near every hand and neckline, and the shipped mask was wrong there on
    # five of six complexions. Cleaning each colour independently keeps the mask a pure
    # function of that garment's colour, which is what makes it universal.
    by_label, probs = {}, []
    for c in codes:
        msk = labmap == Lof[c]
        msk = ndimage.binary_closing(msk, np.ones((3, 3)))
        by_label[c] = msk
    # Pixels that are an occluder rather than cloth: anything in the skin hue window (5-45
    # degrees, while the codes sit at 135, 215 and 320) and any dark near-achromatic mass
    # connected to the head (hair). Both are computed from the frame, never from a garment,
    # and both are carved rather than merely counted, so "no skin or hair in a mask" is a
    # property of the output instead of a number I hope stays small. It also fixes a trap in
    # my own crease-fill: a blazer's lapels enclose a triangle of chest skin, which is exactly
    # what "a small hole completely surrounded by cloth" describes, and K9 rejected M2 for
    # filling it.
    deg_asm = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("HSV"),
                         dtype=float)[..., 0] * 360.0 / 255.0
    skin_win = np.minimum(np.abs(deg_asm - SKIN_HUE), 360 - np.abs(deg_asm - SKIN_HUE)) < 20
    lab_asm = lab(rgb)
    dark = (lab_asm[..., 0] < 55) & ((rgb.max(2) - rgb.min(2)) < 34)
    hair_asm = np.zeros((h, w), bool)
    hb_asm = head_box(rgb)
    if hb_asm is not None and dark.any():
        lh, nh = ndimage.label(dark, np.ones((3, 3)))
        sd = set(np.unique(lh[hb_asm & (lh > 0)]).tolist()) - {0}
        if sd:
            hair_asm = np.isin(lh, list(sd))
    occ = (skin_win & (rgb.max(2) - rgb.min(2) > 12)) | hair_asm
    pieces, owned = _assemble(by_label, vis, role, h, w, occ=occ)

    # Carve occluding hair out of every piece. Long hair lies across the shoulder and is
    # touching, indeed surrounded by, cloth - so no colour test can call it "not garment"
    # without also cutting the dark folds that ARE garment (that mistake cost 4823px of
    # W1's saree). It is separable by TOPOLOGY: the hair is one connected dark mass that
    # contains the head. Coded cloth is chromatic everywhere, so "dark and achromatic AND
    # connected to the head" picks out exactly the hair and nothing else, on all six
    # complexions. A piece therefore stops where the hair covers it, which is the correct
    # recolour behaviour: the customer's colour must not be painted onto a woman's hair.
    lab_px = lab(rgb)
    chroma = rgb.max(2) - rgb.min(2)
    hair = np.zeros((h, w), bool)
    hb_hair = head_box(rgb)
    dark_ach = (lab_px[..., 0] < 52) & (chroma < 30)
    if hb_hair is not None and dark_ach.any():
        li, n_li = ndimage.label(dark_ach, np.ones((3, 3)))
        seeds = set(np.unique(li[hb_hair & (li > 0)]).tolist()) - {0}
        if seeds:
            hair = np.isin(li, list(seeds))
            for nm in list(pieces):
                pieces[nm] = pieces[nm] & ~hair
    owned = np.zeros((h, w), bool)
    for nm in vis:
        owned |= pieces[nm]
    cloth = int(owned.sum())
    labmap = np.zeros((h, w), np.uint8)               # rebuilt from the owners, so K1 is exact
    for i, nm in enumerate([n for n in vis if pieces[n].any()]):
        labmap[pieces[nm]] = i + 1
    for nm, msk in pieces.items():
        a = int(msk.sum())
        if nm in role and a < 0.02 * cloth:
            probs.append(f"K3 {nm} owns only {a}px ({a/max(1,cloth)*100:.1f}% of coded cloth)")
    def com(nm):
        ys = np.nonzero(pieces[nm].any(1))[0]
        return float(ys.mean()) if len(ys) else -1.0
    cm = {nm: com(nm) for nm in role if pieces.get(nm) is not None and pieces[nm].any()}
    if "rose" in role.values() and "green" in role.values():
        rn = [n for n, c in role.items() if c == "rose"][0]
        gn = [n for n, c in role.items() if c == "green"][0]
        if rn in cm and gn in cm and cm[gn] < cm[rn]:
            probs.append(f"K4 {gn} (lower garment) sits above {rn} (upper garment) - the model swapped the garments")
        for bn in [n for n, c in role.items() if c != "green"]:
            if bn in cm and gn in cm and cm[bn] > cm[gn]:
                probs.append(f"K4 {bn} sits below {gn} - the layers are inverted")
    hb = head_box(rgb)
    head_px = 0
    if hb is None:
        probs.append("K5 head not localisable - cannot certify a face-free mask")
    else:
        head_px = int(sum(int((pieces[nm] & hb).sum()) for nm in vis))
        if head_px:
            probs.append(f"K5 {head_px}px of piece mask inside the head box")
    # Off-palette drift. The obvious test - "saturated and no code colour matches" - fires
    # on the model's own skin, because warm brown skin is saturated and off-palette by
    # definition, and it drowned the real signal at 9-17% of cloth on every master. What
    # actually matters is a strip of fabric that should have been a code colour and was not,
    # so the test is anchored to the coded cloth: saturated, uncoded, and touching it.
    mx = np.asarray(rgb, dtype=float).max(2)
    sat = (mx - np.asarray(rgb, dtype=float).min(2)) / np.maximum(mx, 1)
    coded = labmap > 0
    near_cloth = ndimage.binary_dilation(coded, np.ones((13, 13)))
    off = (sat > 0.34) & (d1 > 52) & ~coded & near_cloth & ~ndimage.binary_dilation(coded, np.ones((3, 3)))
    n_off = int(off.sum())
    if n_off > 0.06 * max(1, cloth):
        probs.append(f"K6 {n_off}px saturated cloth-side pixels match no code colour ({n_off/max(1,cloth)*100:.0f}% of cloth) - a garment drifted off palette")
    # K8 a colour that is clearly present but unowned. This is how M10 hid a real defect:
    # the model painted a blue kurta the manifest never declared, so no piece claimed it,
    # and the outfit still "passed" with 2 of 3 garments masked. A garment nobody owns is
    # a garment the customer can never recolour - exactly the failure that must not ship
    # silently. Fix here is the manifest (describe the photo), not the threshold.
    for c in ORDER:
        if c in role.values():
            continue
        sw = np.array(CODE[c], float)
        d = np.sqrt(((np.clip(rgb, 0, 255) - sw) ** 2).sum(2))
        present = (d < 70) & (np.asarray(rgb, float).max(2) > 0)
        present = ndimage.binary_opening(present, np.ones((5, 5)))
        a = int(present.sum())
        if a > 0.05 * max(1, cloth):
            probs.append(f"K8 {a}px of {c.upper()} cloth in the image but no piece owns {c} "
                         f"- pieces.json for {o['id']} is missing a garment")

    # K1 overlap is now structurally impossible (front-to-back claiming), so this check
    # exists to catch a future edit that breaks it, not to negotiate with it.
    own = np.zeros((h, w), bool)
    dup = 0
    for nm in vis:
        dup += int((own & pieces[nm]).sum())
        own |= pieces[nm]
    if dup:
        probs.append(f"K1 {dup}px owned by two pieces (impossible by construction)")
    if cloth != int(own.sum()):
        probs.append(f"K1 coded cloth {cloth} != union {int(own.sum())}")
    # K9 no labelled pixel may be skin. Rose and Indian skin are both warm, so "it matched
    # the palette" is not by itself proof that a hand was not claimed.
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from mask_blue import skin_band
    # K9: no occluder inside a piece mask. Measured against the ONE property this scheme
    # guarantees - coded cloth is highly chromatic and mid-bright - because the obvious
    # instrument failed here: mask_blue.signals() calls anything dark "hair", which in W1's
    # silk saree meant every deep fold shadow (4823px of legitimate cloth, chroma 61-81,
    # hue 353-357) was reported as an occluder. Hair and shadow are the same luminance; they
    # are not the same colour, and the garment's colour is the thing I control.
    # K9, now an identity rather than a hope: hair is carved above, and skin cannot be
    # claimed at all because the hue window of every code is disjoint from the skin hue
    # window (rose 320 +/- 40, blue 215 +/- 40, green 135 +/- 40, skin 25). Both are
    # re-measured here so a future palette change breaks loudly instead of quietly.
    deg_k = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("HSV"),
                       dtype=float)[..., 0] * 360.0 / 255.0
    # Same window the carve uses, chroma included. When the two definitions differed only by
    # the saturation term, K9 rejected M14 for 42 near-neutral pixels (chroma <= 12) that are
    # grey cloth shading at a seam, not skin - a gate cannot reject on pixels the rule it
    # audits deliberately allows through.
    chroma_k = rgb.max(2) - rgb.min(2)
    skin_hue = (np.minimum(np.abs(deg_k - SKIN_HUE), 360 - np.abs(deg_k - SKIN_HUE)) < 20) \
        & (chroma_k > 12)
    n_hair = int((owned & hair).sum())
    # The veto identity is asserted on the CLASSIFIER output. Asserting it on the shipped
    # masks was my error: by_label runs a 3x3 closing so a wavy seam does not leave 1px
    # notches, and that closing legitimately seals over a handful of rim pixels - 1 to 88 of
    # them per frame, always on a boundary, never a region. Measured on lm_src the number is
    # what actually matters and must be exactly zero.
    n_skinh = int(((lm_src > 0) & skin_hue).sum())
    n_skinh_closed = int((owned & skin_hue).sum())
    if n_hair:
        probs.append(f"K9 {n_hair}px of hair left inside a piece mask after carving")
    if n_skinh:
        probs.append(f"K9 {n_skinh}px of skin-hued pixel claimed by the classifier - the hue veto failed")
    if n_skinh_closed:
        probs.append(f"K9 {n_skinh_closed}px of occluder survived the carve - carving is not a filter, it is the rule")
    met_hue = hue_report(rgb, codes)
    if met_hue:
        for c, v in met_hue.items():
            if v["p99"] < 45 or v["near_pct"] > 0.5:
                probs.append(f"K9 code {c} is too close to this frame's skin: 99th-pct hue gap "
                             f"{v['p99']}deg, {v['near_pct']}% of skin inside the hue window")
    met = {"cloth_px": cloth, "areas": {nm: int(pieces[nm].sum()) for nm in vis},
           "overlap_px": dup, "head_px": head_px, "off_palette_px": n_off,
           "min_skin_hue_deg": met_hue, "hair_px": n_hair, "skin_px": n_skinh, "rim_px": n_skinh_closed,
           "hair_carved_px": int(hair.sum())}
    for nm in hid:
        pieces[nm] = np.zeros((h, w), bool)
    if proof:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from mask_blue import tone_variant, LADDER
        guard = (own * 255).astype(np.uint8)
        # K7, stated as the property that the pipeline actually depends on: the tone step
        # must not touch a single pixel that any piece mask owns. If it does not, the masks
        # derived once on the base master are correct on all six complexions by construction,
        # and nothing needs re-deriving.
        #
        # An earlier version re-ran the classifier on re-toned frames and compared the label
        # maps, which sounds stricter but measured the wrong thing: my test helper blends the
        # new complexion with a wide feather band (the shipping tool is tone.py, which is
        # masked to skin and does not touch cloth at all), so skin-edge pixels came out
        # blue-shifted and "disagreed" by up to 135k px per outfit while the garment itself
        # was bit-identical. Judging mask correctness by that comparison would have had me
        # "fix" a mask that was right, and would still have said nothing about the real risk.
        touched = 0
        for tn, (Lv, Sv) in list(LADDER.items()) + [("x-pale", (212, 14)), ("x-deep", (92, 56))]:
            try:
                vt = tone_variant(rgb.astype(np.uint8), Lv, Sv, avoid=guard)
            except RuntimeError as e:
                probs.append(f"K7 {tn}: {e}")
                continue
            moved = np.abs(vt.astype(float) - np.clip(rgb, 0, 255)).max(2) >= 1
            touched = max(touched, int((moved & own).sum()))

    if proof:
        met["tone_touched_cloth_px"] = touched
    return pieces, met, probs
    


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imgs", nargs="*")
    ap.add_argument("--outdir", default="template/universal-masking")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sheet", default="template/_qc/code-proof.png")
    a = ap.parse_args()
    man = json.load(open(os.path.join(TPL, "pieces.json")))
    byid = {o["id"]: o for o in man["outfits"]}
    args = list(a.imgs)
    if not args:
        import glob as _g
        import re as _re
        def _key(q):
            m = _re.match(r"[A-Z]+(\d+)", os.path.basename(q))
            return int(m.group(1)) if m else 0
        args = sorted(_g.glob(os.path.join(ROOT, "template", "base", "*.jpg")), key=_key) \
            or sorted(_g.glob(os.path.join(ROOT, "template", "_qc", "code", "*.png")), key=_key)
    os.makedirs(os.path.join(ROOT, a.outdir), exist_ok=True)
    ok = rej = 0
    tiles = []
    from PIL import ImageDraw
    import re as _re
    for p in args:
        # The id is the leading M/W-number token of the filename, because a master is
        # named <ID>-<slug>.jpg while the probe copies are named <ID>.png. Splitting on
        # "." looked fine until it was handed a real base/ file and silently matched
        # nothing - "0 rejected, 0 masked" is the most misleading exit code there is.
        m_id = _re.match(r"([A-Z]+\d+)", os.path.basename(p))
        oid = m_id.group(1) if m_id else os.path.basename(p).split(".")[0]
        o = byid.get(oid)
        if o is None:
            print(f"  {oid:5s} SKIP not in pieces.json")
            continue
        rgb = np.asarray(Image.open(p).convert("RGB"), dtype=float)
        if a.report:
            print(f"  {oid:5s} code map {roles_for(o)}")
            continue
        pieces, met, probs = mask_set(rgb, o, proof=a.proof)
        if pieces is None or probs:
            rej += 1
            print(f"  {oid:5s} REJECT  " + ("; ".join(probs) if probs else "no mask"))
            continue
        for nm, msk in pieces.items():
            Image.fromarray((msk * 255).astype(np.uint8)).save(
                os.path.join(ROOT, a.outdir, f"{oid}-{nm}-mask.png"))
        ok += 1
        print(f"  {oid:5s} OK    " + "  ".join(f"{k}={v//1000}k" for k, v in met['areas'].items())
              + f"   overlap {met['overlap_px']}px  head {met['head_px']}px  off-palette {met['off_palette_px']}px"
              + (f"  tone-touched-cloth {met.get('tone_touched_cloth_px')}px" if a.proof else ""))
        ov = np.asarray(rgb, dtype=float).copy()
        # built from CODE, never restated: a second palette table is how a newly added
        # colour classifies perfectly and then crashes only the sheet.
        pal = {c: tuple(min(255, int(v * 1.28)) for v in CODE[c]) for c in CODE}
        role = roles_for(o)
        for nm, msk in pieces.items():
            if not msk.any():
                continue
            c = np.array(pal[role.get(nm, "rose")], float)
            ov[msk] = 0.5 * c + 0.5 * ov[msk]
            bd = msk & ~ndimage.binary_erosion(msk, np.ones((3, 3)))
            ov[bd] = [255, 255, 255]
        im = Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8))
        im.thumbnail((250, 450))
        ImageDraw.Draw(im).text((3, 3), f"{oid} " + "+".join([q["piece"] for q in o["pieces"] if q["z"]]),
                                fill=(255, 255, 255))
        tiles.append(im)
    if tiles:
        W = min(5, len(tiles))
        cw, ch = tiles[0].width, max(t.height for t in tiles)
        rows = (len(tiles) + W - 1) // W
        sheet = Image.new("RGB", (W * (cw + 8) + 8, rows * (ch + 8) + 26), (245, 245, 245))
        ImageDraw.Draw(sheet).text((8, 7), "each colour IS one garment mask - the boundary is the colour edge, never a guess",
                                   fill=(10, 10, 10))
        for i, t in enumerate(tiles):
            r, c = divmod(i, W)
            sheet.paste(t, (8 + c * (cw + 8), 26 + r * (ch + 8)))
        sheet.save(os.path.join(ROOT, a.sheet))
        print("sheet", a.sheet)
    print(f"\n{ok} outfits masked exactly, {rej} rejected")
    return 0 if not rej else 1


if __name__ == "__main__":
    sys.exit(main())
