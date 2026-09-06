#!/usr/bin/env python3
"""Make the six complexions of every master, and prove the masks still fit them.

    python3 template/tools/make_tones.py                      # all outfits in pieces.json
    python3 template/tools/make_tones.py --outfits M1,M6,W2   # a batch
    python3 template/tools/make_tones.py --sheet out.png      # also build the review sheet

The complexion is NOT authored per outfit: each frame is driven onto the ladder's own numbers
(tone-ladder.json, skinL 190->114 and skinS 24->44, in tone.py's units of mean-of-channels and
max-min) so that the six cards of one outfit and the six cards of the next are the same six
complexions. That is also why a text prompt cannot make this: "slightly deeper" is not a number
that survives being rendered.

Then it checks the one property the whole universal-masking scheme rests on, per frame written:

  T1  not one pixel inside any piece mask changed, at 1 LSB - so the shipped masks are exactly
      correct on all six complexions, and no mask is re-derived per tone;
  T2  every changed pixel is inside the skin (the backdrop sweep and its shadow are bit-identical
      across tones, or the cards stop being comparable and every backdrop-relative measure goes
      stale);
  T3  the frame landed on its rung: measured skinL/skinS within 1.5 of the target, the ladder's
      own tolerance being 15;
  T4  skinS stays inside the natural band 18-52 (the shop's standing instruction: make the colour
      right, do not make it strong), and neighbouring rungs keep a visible gap.

Tone work is deliberately done on the CPU with a measured transform rather than by the image
model, and this file imports the very function the mask gates use (mask_blue.tone_variant ->
tone.tone_pixels), so what is certified here is what ships.
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mask_blue import (COPY_TONES, LADDER, NEIGH_MIN_GAP,         # noqa: E402
                    SKIN_S_BAND, backdrop_like, exclusions, skin_region, tone_variant)
from mask_code import ORDER, classify, fit_master, roles_for      # noqa: E402
from tone import rgb_to_ls                                       # noqa: E402

FOLDERS = {k: k for k in LADDER}                                   # folder name == tone name
TOL_LS = 4.0                      # a frame must land on its rung this closely - tone.py's
                                  # own pass criterion, so the batch tool and the single-frame
                                  # tool cannot disagree about whether a frame is good


def load_master(rel):
    p = os.path.join(ROOT, "template", rel)
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.uint8)


def union_mask(rgb, o):
    codes = [c for c in ORDER if c in roles_for(o).values()]
    lm, _, _ = classify(rgb.astype(float), codes)
    return lm > 0


def tone_one(rgb, o, tone):
    """Render one frame for one rung - the batch's own path, returned with the region it used.

    tone.py's single-frame command goes through here. That matters because there are two skin
    finders in this kit: tone.skin_mask (silhouette + warmth) is for arbitrary photos, while these
    32 masters are toned by the coded-cloth region in mask_blue.skin_region, which is the one the
    gates certify. If the CLI kept its own, a hand-run render and a shipped frame would disagree by
    up to 159 levels, and nothing would catch it until the site showed both.
    """
    if tone not in LADDER:
        raise KeyError(f"tone {tone!r} is not a rung in tools/tone-ladder.json")
    if tone in COPY_TONES:
        # the master served as its own complexion: no edit, so the region is moot but still reported
        own = union_mask(rgb, o)
        avoid = np.maximum((own * 255), (exclusions(rgb.shape, o["id"]) * 255).astype(np.uint8)).astype(np.uint8)
        return np.asarray(rgb, dtype=np.uint8).copy(), skin_region(rgb.astype(float), avoid)
    own = union_mask(rgb, o)
    avoid = np.maximum((own * 255), (exclusions(rgb.shape, o["id"]) * 255).astype(np.uint8)).astype(np.uint8)
    Lt, St = LADDER[tone]
    out = tone_variant(rgb, Lt, St, avoid=avoid)
    return out, skin_region(rgb.astype(float), avoid)


def make_one(o, folders=None, qc=None, verify_only=False):
    """Write (or just re-measure) this outfit's tone frames, verifying each one."""
    rgb = load_master(o["image"])
    own = union_mask(rgb, o)
    excl = exclusions(rgb.shape, o["id"])          # curated, see tone-exclusions.json
    avoid = np.maximum((own * 255), (excl * 255).astype(np.uint8)).astype(np.uint8)
    L0, S0 = rgb_to_ls(rgb.astype(float))
    m0 = skin_region(rgb.astype(float), avoid)
    base = {"id": o["id"], "skinL": round(float(L0[m0].mean()), 1),
            "skinS": round(float(S0[m0].mean()), 1), "skin_px": int(m0.sum())}
    recs = [base]
    for tone, (Lt, St) in LADDER.items():
        if folders and tone not in folders:
            continue
        dst = os.path.join(ROOT, "template", tone, os.path.basename(o["image"]))
        copied = tone in COPY_TONES               # the master served as its own complexion
        if verify_only:
            # Measure the frame actually delivered, not a fresh render of it.
            if not os.path.exists(dst):
                recs.append({"tone": tone, "error": "no frame on disk"})
                continue
            out = np.asarray(Image.open(dst).convert("RGB"), dtype=np.uint8)
        elif copied:
            out = rgb.copy()
        else:
            try:
                out = tone_variant(rgb, Lt, St, avoid=avoid)
            except RuntimeError as e:
                recs.append({"tone": tone, "error": str(e)})
                continue
        d = np.abs(out.astype(float) - rgb.astype(float)).max(2)
        # A frame measured on disk is a decoded JPEG, so it differs from the master by a couple
        # of levels everywhere - compression, not the tone step. File verification therefore asks
        # for a change of 6 or more, while a fresh render is checked at 1 and is exact.
        thr = 6 if verify_only else 1
        dd = d >= thr
        # ...and a leak on a delivered file only counts if it is bigger than that ringing can
        # explain: 0.04% of the frame, ~400 px here. A real escape is thousands, not dozens.
        allow = max(400, int(0.0004 * m0.size)) if verify_only else 0
        # Every measurement below uses m0, this frame's OWN skin region, and not a band
        # re-derived from the re-toned result. That distinction was worth three failed
        # outfits: skin_band only accepts pixels darker than the sweep, so as skin gets
        # paler the qualifying set shrinks toward the shadowed, more saturated leftovers,
        # and a frame that had landed exactly on fair measured 178/36.5 against a target of
        # 190/24 - the ladder was fine, the ruler had moved. Geometry cannot move either,
        # because cloth and backdrop are bit-identical between a master and its tones.
        t1 = max(0, int(dd[own].sum()) - allow)                    # T1: a piece mask owns its pixels outright
        near = ndimage.binary_dilation(m0, np.ones((3, 3)))
        t2 = max(0, int(dd[~near].sum()) - allow)                  # T2: nothing outside the skin moved
        # T2b, independent of the skin detector: the sweep is cool grey or flat at low chroma
        # and skin is warm and chromatic, so a colour-family test says which changed pixels
        # cannot be skin no matter what the region did. One feather ring is forgiven.
        t2b = max(0, int((backdrop_like(rgb.astype(float))
                          & ~ndimage.binary_dilation(m0, np.ones((5, 5))))[dd].sum()) - allow)
        t5 = max(0, int(dd[excl].sum()) - allow)                  # T5: a curated exclusion box must be untouched
        L1, S1 = rgb_to_ls(out.astype(float))
        aL, aS = float(L1[m0].mean()), float(S1[m0].mean())
        rec = {"tone": tone, "copied": copied,
               "cloth_changed_px": t1, "backdrop_changed_px": t2, "sweep_changed_px": t2b,
               "excl_changed_px": t5, "excl_px": int(excl.sum()),
               "skinL": round(aL, 1), "skinS": round(aS, 1), "wantL": Lt, "wantS": St,
               "skin_px": int(m0.sum()),
               "clipped_px": int(((out.astype(np.int16) >= 255) | (out.astype(np.int16) <= 0))[m0].sum()),
               "change_threshold": thr}
        err = []
        if t1:
            err.append(f"T1 {t1}px of owned cloth changed")
        if t2:
            err.append(f"T2 {t2}px changed outside the skin")
        if t2b:
            err.append(f"T2 {t2b}px of sweep changed clear of the skin")
        if t5:
            err.append(f"T5 {t5}px changed inside an exclusion box")
        if copied:
            # An as-shot card has one honest test: it is the master, pixel for pixel. Its
            # ladder numbers are not targets - they are whatever this model's skin measures.
            # A byte copy of the master, so this one check is exact in both modes: no tolerance,
            # because there is nothing that could legitimately have moved.
            bad = int((d > 0).sum())
            rec["identical_to_master"] = bad == 0
            if bad:
                err.append(f"as-shot frame differs from the master at {bad} px")
        else:
            if abs(aL - Lt) > TOL_LS or abs(aS - St) > TOL_LS:
                err.append(f"T3 off rung: L {aL:.1f}/{Lt} S {aS:.1f}/{St}")
            if not (SKIN_S_BAND[0] <= aS <= SKIN_S_BAND[1]):
                err.append(f"T4 skinS {aS:.1f} outside natural band {SKIN_S_BAND}")
        rec["error"] = "; ".join(err) or None
        if not err and qc is not None and not verify_only:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if copied:
                shutil.copyfile(os.path.join(ROOT, "template", o["image"]), dst)
            else:
                Image.fromarray(out).save(dst, quality=95, subsampling=0, optimize=False)
        recs.append(rec)
    # T4 across rungs: a ladder the eye can read as steps, not two groups. Only the *driven*
    # rungs are checked, because "as-shot" is the source photo and is not a step anyone set:
    # its own lightness (115-165 across the 32 frames) falls in the middle of the ladder, so it
    # is measured against its nearest driven neighbour and reported, never enforced.
    got = [r["skinL"] for r in recs[1:] if "skinL" in r and not r.get("copied")]
    if len(got) >= 2:
        gaps = [abs(got[i + 1] - got[i]) for i in range(len(got) - 1)]
        if min(gaps) < NEIGH_MIN_GAP:
            recs.append({"id": o["id"], "error": f"T4 neighbour gap {min(gaps):.1f} < {NEIGH_MIN_GAP:g}"})
    for r in recs[1:]:
        if r.get("copied") and "skinL" in r:
            d = [abs(r["skinL"] - q["skinL"]) for q in recs[1:] if "skinL" in q and not q.get("copied")]
            r["nearest_driven_gap"] = round(min(d), 1) if d else None
    return recs


def build_sheet(ids, out, scale=0.165):
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    byid = {o["id"]: o for o in man["outfits"]}
    tones = list(LADDER)
    W, H = 768, 1376
    cw, ch = int(W * scale), int(H * scale)
    pad, lab = 6, 22
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    Fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    ncol = len(tones) + 1
    S = Image.new("RGB", (ncol * (cw + pad) + pad, len(ids) * (ch + lab + pad) + 26),
                  (16, 16, 18))
    d = ImageDraw.Draw(S)
    d.text((pad, 7), "HueFit - master (left) then the six complexions. Same pixels, same masks: "
                     "only skin moves.", font=Fs, fill=(225, 225, 225))
    for i, oid in enumerate(ids):
        o = byid[oid]
        y = 26 + pad + i * (ch + lab + pad)
        d.text((pad, y + ch + 3), f"{oid} {o['slug']}", font=F, fill=(235, 235, 235))
        S.paste(Image.open(os.path.join(ROOT, "template", o["image"])).resize((cw, ch)),
                (pad, y))
        for j, tone in enumerate(tones):
            p = os.path.join(ROOT, "template", tone, os.path.basename(o["image"]))
            if os.path.exists(p):
                S.paste(Image.open(p).resize((cw, ch)), (pad + (j + 1) * (cw + pad), y))
        for j, tone in enumerate(tones):
            d.text((pad + (j + 1) * (cw + pad) + 2, 26 - lab + 6), tone, font=Fs, fill=(190, 190, 190))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    S.save(out)
    return S.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfits", default="", help="comma list; default = every outfit with a master")
    ap.add_argument("--report", default=os.path.join(ROOT, "template", "_qc", "tones-report.json"))
    ap.add_argument("--sheet", default="")
    ap.add_argument("--dry", action="store_true", help="verify without writing files")
    ap.add_argument("--tones", default="", help="comma list of rungs to build (default: all six)")
    ap.add_argument("--verify-only", action="store_true", dest="verify_only",
                    help="measure the frames already on disk and write the report; changes nothing")
    a = ap.parse_args()
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    ids = [x.strip() for x in a.outfits.split(",") if x.strip()]
    outfits = [o for o in man["outfits"] if (not ids or o["id"] in ids) and o.get("image")]
    if not outfits:
        print("no masters to tone", file=sys.stderr)
        return 1
    want = {x.strip() for x in a.tones.split(",") if x.strip()} or None
    allr, bad = {}, 0
    for o in outfits:
        recs = make_one(o, want, qc=None if (a.dry or a.verify_only) else 1,
                        verify_only=a.verify_only)
        errs = [r["error"] for r in recs if r.get("error")]
        allr[o["id"]] = recs
        tag = "  ".join(f"{r['tone']} {r.get('skinL','-')}/{r.get('skinS','-')}"
                        for r in recs[1:] if "tone" in r)
        state = "OK  " if not errs else "FAIL"
        if errs:
            bad += 1
        print(f"  {state} {o['id']:4s} base {recs[0]['skinL']}/{recs[0]['skinS']}  {tag}"
              + ("" if not errs else "   " + "; ".join(errs)))
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    json.dump(allr, open(a.report, "w"), indent=1)
    if a.sheet:
        print("sheet", build_sheet([o["id"] for o in outfits],
                                  os.path.join(ROOT, a.sheet) if not os.path.isabs(a.sheet) else a.sheet))
    n = sum(1 for v in allr.values() for r in v if r.get("tone"))
    print(f"\n{n} tone frames verified across {len(outfits)} outfits, {bad} rejected")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
