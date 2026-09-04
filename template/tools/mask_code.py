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
  K4 role geometry: green's centre of mass must be below rose's, blue between them.
     A swap means the model mis-assigned garments, which would silently put the
     customer's trouser colour on the jacket.
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
ORDER = ["rose", "blue", "green"]          # outermost/top -> middle -> bottom
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
    ok = (d1 < 52) & ((d2 - d1) > 9) & (hd_best < HUE_CAP)
    lm = np.where(ok, (nearest + 1).astype(np.uint8), np.uint8(0)).astype(np.uint8)
    return lm, d1


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


def _assemble(by_label, vis, role, h, w):
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
        pieces[nm] = msk
        owned |= msk
    return pieces, owned


def roles_for(o):
    """colour -> piece for this outfit: bottom garment is green, topmost visible is
    rose, the next one down is blue, and a fourth (rare) folds into rose."""
    vis = [p["piece"] for p in o["pieces"] if p["z"]]
    if not vis:
        return {}
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
    labmap, d1 = classify(rgb, codes)
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
    pieces, owned = _assemble(by_label, vis, role, h, w)
    cloth = int(owned.sum())
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
            probs.append(f"K4 {gn} (green) sits above {rn} (rose) - the model swapped the garments")
        bn = [n for n, c in role.items() if c == "blue"]
        if bn and bn[0] in cm and gn in cm and cm[bn[0]] > cm[gn]:
            probs.append(f"K4 middle layer {bn[0]} sits below {gn} - the layers are inverted")
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
    from mask_blue import signals as _sig
    _, sk_h, hr_h, _, _, _ = _sig(np.clip(rgb, 0, 255).astype(np.uint8))
    n_skin = int((own & (sk_h | hr_h) & ~ndimage.binary_dilation(~own, np.ones((3, 3)))).sum())
    if n_skin > 0.0008 * max(1, cloth):
        probs.append(f"K9 {n_skin}px of piece mask is skin/hair deep inside the cloth")
    met_hue = hue_report(rgb, codes)
    if met_hue:
        for c, v in met_hue.items():
            if v["p99"] < 45 or v["near_pct"] > 0.5:
                probs.append(f"K9 code {c} is too close to this frame's skin: 99th-pct hue gap "
                             f"{v['p99']}deg, {v['near_pct']}% of skin inside the hue window")
    met = {"cloth_px": cloth, "areas": {nm: int(pieces[nm].sum()) for nm in vis},
           "overlap_px": dup, "head_px": head_px, "off_palette_px": n_off,
           "min_skin_hue_deg": met_hue, "deep_skin_px": n_skin}
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
        pal = {"rose": (232, 76, 140), "blue": (60, 130, 235), "green": (60, 200, 110)}
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
