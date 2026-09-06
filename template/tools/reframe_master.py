"""Audit and repair the framing of a master whose figure is cut by the frame edge.

M4 is the case that produced this file. His render put the hair at row 0 and the shoe soles at row
1375, so both ends were amputated - the catalogue's framing rule (measured below) was broken for him
alone, and every card made from him inherited it. The user's words: "in m4 model there is over crop
image problem".

House framing, measured over the 32 masters' coded garment rows:
    figure height median 1237 rows, headroom 77, footroom 58

Two design decisions, both from failures in this file's first draft:

* the missing crown and soles are NOT synthesised here. Mirroring the pixels beside a cut upward looks
  like a studio trick because it is one - on M4 it reproduced his eyebrows and eyes above his hairline
  and produced a monster. The repair is a re-frame by the image model; this tool's job is to prove the
  candidate is the same photograph (garment areas within tolerance, codes still classifying) before it
  is allowed to become a master, and to back the old one up;
* the audit reads the figure through the same colour classifier the masks use, because the obvious
  shortcut - "anything not backdrop is body" - is wrong on these frames in both directions: the coded
  green of a trouser leg passes `backdrop_like` (B >= R-2), and the floor's pooled shadow under a hem is
  genuinely non-backdrop. Measuring with the ruler the pipeline actually trusts is the only version of
  this that agrees with the eye.

  python3 template/tools/reframe_master.py --check
  python3 template/tools/reframe_master.py --check --outfit M4
  python3 template/tools/reframe_master.py --install CAND.png --outfit M4
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from mask_code import classify, mask_set, roles_for          # noqa: E402
from mask_blue import skin_region                             # noqa: E402

T = os.path.join(ROOT, "template")
H, W = 1376, 768
CODES = ["rose", "blue", "green"]
CROWN_ROWS, SOLE_ROWS = 46, 26     # invented caps: hair above the cut, soles below it
HOUSE = {"height": 1237, "headroom": 77, "footroom": 58}
MIN_HEADROOM, MIN_FOOTROOM = 40, 25      # below these the card reads as cropped


def manifest():
    return json.load(open(os.path.join(T, "pieces.json")))["outfits"]


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=float)


def figure(rgb, o):
    """Rows/cols of the actual figure, via the classifier + the skin region + hair/shoe darkness.

    `dark` is restricted to the rows between the top of the clothes and the bottom of them plus a
    margin, which is where hair and shoes live, precisely so the floor shadow below a hem cannot be
    read as a truncated foot.
    """
    present = [c for c in CODES if c in roles_for(o).values()]
    lm, _, _ = classify(rgb, present)
    coded = lm > 0
    sk = skin_region(rgb, np.where(coded, 255, 0).astype(np.uint8))
    lum = rgb.mean(2)
    ys = np.nonzero(coded.sum(1) >= 12)[0]
    if not ys.size:
        return None
    lo, hi = max(0, int(ys.min()) - 260), min(H, int(ys.max()) + 40)
    xs = np.nonzero(coded.any(0))[0]
    c0, c1 = max(0, int(xs.min()) - 70), min(W, int(xs.max()) + 70)
    dark = np.zeros_like(coded)
    dark[lo:hi, c0:c1] = (lum[lo:hi, c0:c1] < 112)
    body = coded | sk | dark
    rows = np.nonzero(body.sum(1) >= 12)[0]
    return {"coded_rows": (int(ys.min()), int(ys.max())), "rows": (int(rows.min()), int(rows.max())),
            "cols": (c0, c1),
            # keyed off the codes this outfit actually wears, in the order classify() got them - a fixed
            # CODES index mislabels every garment on a frame that is missing one code
            "areas": {c: int((lm == k + 1).sum()) for k, c in enumerate(present)}}


def _max_run(vec):
    """Widest contiguous stretch of True in a 1-D mask."""
    if not vec.any():
        return 0
    c = np.diff(np.concatenate(([0], vec.astype(np.int8), [0])))
    st = np.nonzero(c == 1)[0]
    en = np.nonzero(c == -1)[0]
    return int((en - st).max()) if st.size else 0


def verdicts(rgb, o):
    """A figure is CUT when near-black material at the edge is as wide as it is inside the frame.

    Three rulers were tried before this one and each was wrong in a way I could see but not trust:
    "anything not backdrop" counted the coded green trouser legs (backdrop_like accepts them) and the
    floor's pooled shadow, so it called W10's intact heels cut; "a wide contiguous run" missed M4's
    actual cut because a hairline at the crop line is a fringe of strands, not a solid bar; and raw
    coverage flagged M9, whose black shoes taper to a soft contact shadow. What separates a scissor
    line from a shoe on a floor is direction: material severed by the frame is at least as wide at the
    last row as it is 7 rows inside (ratio ~1.1 on M4), while an intact one narrows into its own
    shadow (0.82 on M9). Threshold 0.95, and only near-black counts, so a grey sweep cannot register.
    """
    f = figure(rgb, o)
    if f is None:
        return f, ["NO CLOTH FOUND"]
    lum = rgb.mean(2)
    c0, c1 = f["cols"]

    def band(rows, thr=80.0):
        return float(np.mean([int((lum[r, c0:c1] < thr).sum()) for r in rows]))

    top_edge, top_in = band([0, 1, 2]), band(range(6, 13))
    bot_edge, bot_in = band([H - 1, H - 2, H - 3]), band(range(H - 13, H - 7))
    v = []
    if top_edge >= 40 and top_edge >= 0.95 * top_in:
        v.append("CROWN CUT")
    elif f["rows"][0] < 24:
        v.append("tight headroom")
    if bot_edge >= 40 and bot_edge >= 0.95 * bot_in:
        v.append("FEET CUT")
    elif H - 1 - f["rows"][1] < 24:
        v.append("tight footroom")
    return f, v


def pad(oid, out, headroom=70, footroom=45, crown=CROWN_ROWS, sole=SOLE_ROWS):   # crown/sole=0 -> pure geometry, nothing invented
    """Scale the figure to house framing and fill what the frame has no room for with backdrop.

    Nothing is invented here on purpose - a mirrored hairline produced a second pair of eyebrows. The
    padded bands are flat sweep, which is the right input to hand to an image model: it only has to
    finish a hairline and a shoe sole, not recompose a photograph it will not recompose.

    All of it is computed in the scaled frame's own coordinates and then widened, so the side bands of
    the padded rows are the same edge-column replication the figure rows already use: mixing the two
    conventions is what drew a line across the whole width of the first attempt.
    """
    o = [x for x in manifest() if x["id"] == oid][0]
    src = load(os.path.join(T, o["image"]))
    f = figure(src, o)
    if f is None:
        print("FAIL: no garments classified on this master")
        return 1
    top, bot = f["rows"]
    # Two ceilings on the scale, both decided before anything is measured, because measuring the first
    # small render and then re-scaling left the stale mask columns pointing at the wrong width:
    #   height  - bring the figure up to the house median so all 32 cards match
    #   fit     - the padded figure, headroom and footroom must all still live inside 1376 rows
    sc = min(1.0,
             (HOUSE["height"] - (crown + sole)) / max(1, bot - top),
             (H - headroom - footroom) / max(1, bot - top))
    sw, sh = int(round(W * sc)), int(round(H * sc))
    small = np.asarray(Image.fromarray(np.clip(src, 0, 255).astype(np.uint8)).resize((sw, sh),
                                                                                      Image.LANCZOS),
                       dtype=float)
    from mask_code import classify as _cl
    lm, _, _ = _cl(small, [c for c in CODES if c in roles_for(o).values()])
    occupied = (lm > 0) | skin_region(small, (255 * (lm > 0)).astype(np.uint8))
    occ_cols = occupied.any(0)
    lum_s = small.mean(2)
    # a column can supply backdrop to the band only if the figure is not in it and the pixel is light
    ok = (~occ_cols) & (lum_s[0] >= 120)
    ok_b = (~occ_cols) & (lum_s[-1] >= 120)

    def ramp(mask, src_row):
        out = src_row.astype(float).copy()
        bad = ~mask
        if int(mask.sum()) < 2 or not bad.any():
            return out
        xs = np.nonzero(mask)[0]
        for c in range(3):
            out[bad, c] = np.interp(np.arange(sw), xs, src_row[xs, c])[bad]
        return out

    if int(ok.sum()) < 2:
        ok = ~occ_cols
    if int(ok_b.sum()) < 2:
        ok_b = ~occ_cols
    x0 = (W - sw) // 2
    # Align the FIGURE to the house headroom, not its frame: on a cut master the figure starts at row 0
    # so y0 lands at headroom+crown, while on a whole-but-cramped one (M2's top is at row 34) the same
    # formula would push its feet out of the bottom and manufacture the very defect being repaired.
    y0 = max(0, int(round(headroom - top * sc + crown)))
    ybot = min(H, y0 + sh)
    nrows = ybot - y0

    def widen(row):
        return np.concatenate([np.repeat(row[0][None, :], x0, 0), row,
                               np.repeat(row[-1][None, :], W - x0 - sw, 0)], 0)

    fill_t, fill_b = widen(ramp(ok, small[0])), widen(ramp(ok_b, small[-1]))
    z = np.zeros((H, W, 3))
    z[:y0] = fill_t[None, :, :]
    z[ybot:] = fill_b[None, :, :]
    for r in range(nrows):
        z[y0 + r] = widen(small[r])
    z[y0:ybot, x0:x0 + sw] = small[:nrows]
    Image.fromarray(np.clip(z, 0, 255).astype(np.uint8)).save(out)
    json.dump({"scale": sc, "x0": x0, "y0": y0, "ybot": ybot, "sw": sw, "sh": sh,
               "crown": crown, "sole": sole, "padded": os.path.abspath(out)},
              open(out.rsplit(".", 1)[0] + "-marks.json", "w"), indent=1)
    print(f"  padded {os.path.relpath(out, ROOT)}  scale {sc:.3f}  figure rows {y0}->{ybot} ({ybot-y0}); "
          f"cut line at {y0} (crown band {y0-crown}-{y0}) and {ybot} (sole band {ybot}-{ybot+sole})")
    return 0


def restore(oid, gen, marks_path, ov=16, feather=10):
    """Keep only the bands the model was asked to author; the rest comes back from the padded master.

    A generative pass will happily re-light a lapel or thicken a tie while doing what it was asked to do,
    and nothing downstream notices - the masks classify whatever colours arrive. So the approved pixels
    are pasted back everywhere except the two invented bands, which makes drift structurally impossible
    rather than something to spot.

    The first version pasted those bands as hard rectangles and the result had a visible line across his
    forehead. Two changes fix it: the band reaches `ov` rows *into* the master's own hair and shoes, so
    the two hairlines overlap where the texture is continuous rather than meeting at the cut; and the
    weight ramps linearly over `feather` rows at each edge, which is also what hides the small tone
    difference between the model's beige and the fill's beige.
    """
    mk = json.load(open(marks_path))
    z = np.asarray(Image.open(gen).convert("RGB"), dtype=float)
    if z.shape != (H, W, 3):
        print(f"FAIL: {gen} is {z.shape[1]}x{z.shape[0]}, expected {W}x{H} - the model recomposed instead\n"
              f"      of extending, and a resized frame would move every garment off its mask, so it is\n"
              f"      rejected here rather than squashed into shape")
        return None
    base = np.asarray(Image.open(mk["padded"]).convert("RGB"), dtype=float)
    y0, ybot = mk["y0"], mk["ybot"]
    wt = np.zeros(H)
    spans = [(max(0, y0 - mk["crown"] - feather), y0 + ov), (ybot - ov, min(H, ybot + mk["sole"] + feather))]
    for a, b in spans:
        for r in range(a, b):
            up = min(1.0, (r - a) / feather) if feather else 1.0
            dn = min(1.0, (b - r) / feather) if feather else 1.0
            wt[r] = max(wt[r], min(up, dn))
    w3 = wt[:, None, None]
    out = base * (1 - w3) + z * w3
    dst = os.path.join(T, "_qc", f"{oid}-restored.png")
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dst)
    rows = np.nonzero(wt > 0.5)[0]
    print(f"  restored {os.path.relpath(dst, ROOT)}: the render is kept at rows {rows.min()}-{rows.max()} "
          f"(feathered, overlapping the master by {ov} rows at each cut), every other row is the approved master")
    print(f"  blended rows {int((wt>0).sum())}, fully authored {int((wt>=0.999).sum())}")
    return dst


def check(only=""):
    """Print the framing of every master, so an over-crop is a finding and not a complaint."""
    print(f"house framing: figure height median {HOUSE['height']}, headroom {HOUSE['headroom']}, "
          f"footroom {HOUSE['footroom']}   (tight = under {MIN_HEADROOM}/{MIN_FOOTROOM} rows)")
    print(f"{'id':4s} {'fig rows':>13s} {'height':>7s} {'head':>5s} {'foot':>5s}   verdict")
    flagged = []
    for o in manifest():
        if only and o["id"] != only:
            continue
        f, v = verdicts(load(os.path.join(T, o["image"])), o)
        if f is None:
            print(f"{o['id']:4s} {'-':>13s} {'-':>7s} {'-':>5s} {'-':>5s}   {' '.join(v)}")
            flagged.append(o["id"])
            continue
        top, bot = f["rows"]
        if v:
            flagged.append(o["id"])
        print(f"{o['id']:4s} {str(f['rows']):>13s} {bot-top:7d} {top:5d} {H-1-bot:5d}   {' '.join(v) or 'ok'}")
    print("\nflagged:", flagged or "none - every figure is whole inside its frame")
    return flagged


def install(oid, cand):
    """Put a re-framed render in place of a master - only if it is provably the same photograph."""
    o = [x for x in manifest() if x["id"] == oid]
    if not o:
        print(f"FAIL: {oid} is not in pieces.json")
        return 1
    o = o[0]
    z = load(cand)
    if z.shape != (H, W, 3):
        print(f"FAIL: candidate is {z.shape[1]}x{z.shape[0]}, masters are {W}x{H}. Resizing it to fit "
              "would move every garment off its mask, so it is rejected instead.")
        return 1
    old = load(os.path.join(T, o["image"]))
    fo, fn = figure(old, o), figure(z, o)
    if fn is None:
        print("FAIL: the candidate's garments do not classify into the colour codes - it would leave no masks")
        return 1
    f, v = verdicts(z, o)
    hard = [x for x in v if "CUT" in x]
    if hard:
        print(f"FAIL: the candidate still reads as cropped: {hard}")
        return 1
    if v:
        print(f"  note: {v} - inside tolerance, worth an eye")
    print(f"  framing  before {fo['rows']} h {fo['rows'][1]-fo['rows'][0]} head {fo['rows'][0]} "
          f"foot {H-1-fo['rows'][1]}")
    print(f"           after  {fn['rows']} h {fn['rows'][1]-fn['rows'][0]} head {fn['rows'][0]} "
          f"foot {H-1-fn['rows'][1]}")
    # The invariant is not "the areas are near the old ones" - the figure was just rescaled, so they are
    # supposed to change. It is that every garment scales by the SAME factor: a render that quietly
    # recoloured the waistcoat, or folded his arm in, moves one code and not the others. Measuring the
    # scale off the figure rows instead (an earlier draft) produced a bogus +9.4% drift on a perfect
    # re-frame, because the before-rows include hair and soles that the cut had already eaten.
    r = {c: max(1.0, b) / max(1.0, fo["areas"][c]) for c, b in fn["areas"].items() if fo["areas"][c] > 400}
    for c, b in fn["areas"].items():
        print(f"  {c:6s} area {fo['areas'][c]:8d} -> {b:8d}   ratio {b/max(1,fo['areas'][c]):.3f}")
    if len(r) >= 2:
        spread = max(r.values()) / min(r.values())
        print(f"  garment areas scale by a common factor within {100*(spread-1):.1f}%")
        if spread > 1.15:
            print("FAIL: the pieces did not scale together - the outfit itself changed, not just its framing.")
            return 1
    if min(r.values()) < 0.35 or max(r.values()) > 2.8:
        print("FAIL: the implied scale is not a framing change.")
        return 1
    pieces, met, probs = mask_set(z, o, proof=False)
    if probs or pieces is None:
        print("FAIL: the mask gates reject the candidate: " + "; ".join(probs))
        return 1
    print(f"  masks    re-derive cleanly on the candidate: overlap {met['overlap_px']}px  "
          f"head {met['head_px']}px  off-palette {met['off_palette_px']}px")
    bak = os.path.join(T, "_qc", f"{oid}-before-reframe.jpg")
    shutil.copyfile(os.path.join(T, o["image"]), bak)
    Image.fromarray(np.clip(z, 0, 255).astype(np.uint8)).save(os.path.join(T, o["image"]),
                                                              quality=95, subsampling=0)
    print(f"  INSTALLED {o['image']}   (previous master kept at {os.path.relpath(bak, ROOT)})")
    print("  everything downstream is derived from this file, so re-run:")
    print(f"    python3 template/tools/mask_code.py {o['image']}")
    print(f"    python3 template/tools/make_tones.py --outfits {oid}")
    print( "    python3 template/tools/make_tones.py --verify-only")
    print( "    python3 template/tools/mask_sheet.py && python3 template/tools/tone_sheets.py")
    return 0


def annotate(oid, out=None):
    """Side-by-side of the master and what the framing ruler sees, for the eye to overrule the numbers."""
    o = [x for x in manifest() if x["id"] == oid][0]
    f, v = verdicts(load(os.path.join(T, o["image"])), o)
    im = Image.open(os.path.join(T, o["image"])).convert("RGB")
    d = ImageDraw.Draw(im)
    top, bot = f["rows"]
    d.line([(0, top), (W, top)], fill=(0, 230, 255), width=3)
    d.line([(0, bot), (W, bot)], fill=(255, 80, 80), width=3)
    d.text((8, top + 6), f"figure top {top}  headroom {top}", fill=(0, 230, 255),
           font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18))
    d.text((8, bot - 26), f"figure bottom {bot}  footroom {H-1-bot}", fill=(255, 120, 120),
           font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18))
    p = out or os.path.join(T, "_qc", f"{oid}-framing.png")
    im.save(p)
    print(f"{os.path.relpath(p, ROOT)}  {' '.join(v) or 'ok'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="audit every master (or one with --outfit)")
    ap.add_argument("--install", default="", help="candidate re-frame to put in place of a master")
    ap.add_argument("--outfit", default="")
    ap.add_argument("--annotate", action="store_true")
    ap.add_argument("--pad", default="", help="write a padded frame (right geometry, no invention) here")
    ap.add_argument("--crown", type=int, default=CROWN_ROWS, help="rows of hair to be invented above the "
                    "cut; 0 for a figure that is whole but cramped, where nothing has to be invented")
    ap.add_argument("--sole", type=int, default=SOLE_ROWS, help="rows of sole to be invented below the cut")
    ap.add_argument("--restore", default="", help="generated frame whose two invented caps are kept")
    a = ap.parse_args()
    if a.pad:
        return pad(a.outfit, a.pad, crown=a.crown, sole=a.sole)
    if a.restore:
        d = restore(a.outfit, a.restore, os.path.join(T, "_qc", f"{a.outfit}-padded-marks.json"))
        return 0 if d else 1
    if a.install:
        return install(a.outfit, a.install)
    if a.annotate:
        return annotate(a.outfit)
    bad = check(a.outfit)
    return 1 if any(x in str(bad) for x in ()) else 0


if __name__ == "__main__":
    sys.exit(main())
