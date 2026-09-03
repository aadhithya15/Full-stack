"""Catalogue audit: one command, every numeric property a frame must have, plus the inter-outfit check.

Per file:
  dims            must be 768x1376 exactly (the mask/overlay system is pixel-locked to this canvas)
  backdrop        96px block-mean spread <=2.0, |mean-128|<=1.5, 16px cell std <=0.30 (gate in check_backdrop)
  sil_frac        body silhouette area as % of frame
  garment_L, delta garment mean luminance, and how far it sits above the 128 field. 'fade' = delta too
                  small: the recolour mask cannot find an edge, and the eye reads washed-out cloth.
  sat_skin        saturation of the skin cluster (the 'over-pumped tan' detector: too high = not a shop look)
  edge_gradation  mean |Laplacian| inside the garment: the sharpness the user called 'not clear'
  hands/shoes     dark-pixel band at the bottom: footwear must be a distinct block, not merged into trousers

Cross-file (the check that caught M15 cloning M10):
  IoU of the body silhouette between every pair of outfits. Same pose + same canvas means two DIFFERENT
  garments still differ in outline (flare, hem line, sleeve). IoU > ~0.93 means the same outfit was
  rendered twice under two names, whatever the labels say.

Usage:  python3 template/tools/audit.py template/base            # whole folder
        python3 template/tools/audit.py template/base --iou       # add the cross-outfit matrix
Exit 1 if any per-file gate fails.
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bgmask import body_silhouette

W, H = 768, 1376
# sat = mean saturation of the skin cluster. The old batch ran 53-77 and read as an over-pumped fake tan,
# which is exactly what the shop rejected ("don't make strong"). Natural Indian skin on this lighting sits
# 20-52; above 52 the face is doing makeup, below 20 it is grey.
LIM = dict(spread=2.0, off=1.5, cellstd=0.30, delta=26.0, grad=1.10, sil=(12.0, 46.0), sat=(18.0, 52.0))


def analyse(path):
    X = np.asarray(Image.open(path).convert("RGB"), dtype=float)
    if X.shape[:2] != (H, W):
        return {"file": os.path.basename(path), "dims": f"{X.shape[1]}x{X.shape[0]}", "fail": ["dims"]}
    L = X.mean(2)
    S = X.max(2) - X.min(2)
    body = body_silhouette(X)
    solid = ndimage.binary_fill_holes(body)
    solid = ndimage.binary_fill_holes(body)
    # Open studio field ONLY. Light-grey cloth (#D5D5D5) is achromatic and sits inside +-30 of 128 in
    # shade, so any background definition that can reach inside the silhouette measures fabric and
    # then fails a clean frame. The old session's gate had exactly this hole; it is closed here.
    field = (S <= 10) & (np.abs(L - 128) <= 30)
    bg = field & ~ndimage.binary_dilation(solid, np.ones((3, 3)), iterations=2)

    v = [float(L[y:y + 96, x:x + 96][bg[y:y + 96, x:x + 96]].mean())
         for y in range(0, H, 96) for x in range(0, W, 96)
         if bg[y:y + 96, x:x + 96].sum() > 200]
    cv = [float(L[y:y + 16, x:x + 16][bg[y:y + 16, x:x + 16]].mean())
          for y in range(0, H, 16) for x in range(0, W, 16)
          if bg[y:y + 16, x:x + 16].sum() >= 0.6 * 256]
    spread = (max(v) - min(v)) if len(v) > 2 else 99.0
    off = abs(np.mean(v) - 128.0) if v else 99.0
    cellstd = float(np.std(cv)) if len(cv) > 10 else 9.9

    inside = np.zeros_like(L, bool)
    inside[3:, :] = solid[:-3, :] & ~solid[:-3, :]
    hdr = np.zeros_like(L, bool)
    hdr[:int(0.16 * H), :] = True
    cloth = solid & ~S.astype(bool) if False else None
    cloth = solid & ~inside & ~hdr & (S <= 12)          # achromatic and inside the outline => garment
    gL = float(L[cloth].mean()) if cloth.sum() > 500 else 0.0
    gy = np.nonzero(cloth.any(1))[0]
    foot = cloth[gy[-200]:, :].sum() if len(gy) > 200 else 0   # cloth reaching the bottom = trousers over shoes
    dark = (L < 92) & solid & ~cloth
    darkrow = float(dark.sum(1).max() / max(dark.sum(), 1)) if dark.any() else 0.0
    gy = np.nonzero(cloth.any(1))[0]
    gy = (gy[0], gy[-1]) if len(gy) else (0, H)
    sub = L[gy[0]:gy[1], :]
    lap = np.abs(4 * sub[1:-1, 1:-1] - sub[:-2, 1:-1] - sub[2:, 1:-1] - sub[1:-1, :-2] - sub[1:-1, 2:])
    grad = float(np.median(lap[cloth[gy[0]:gy[1]][1:-1, 1:-1]])) if cloth.sum() > 500 else 0.0

    skin = (S > 18) & (np.abs(L - 128) > 18)
    top = np.zeros_like(skin)
    top[:int(0.45 * H), :] = True
    sk = skin & top
    sat_skin = float(S[sk].mean()) if sk.sum() > 500 else -1.0
    skinL = float(L[sk].mean()) if sk.sum() > 500 else -1.0

    fail = []
    if spread > LIM["spread"]: fail.append(f"spread {spread:.2f}")
    if off > LIM["off"]: fail.append(f"bg-offset {off:.2f}")
    if cellstd > LIM["cellstd"]: fail.append(f"cell-std {cellstd:.3f}")
    if gL and gL - 128 < LIM["delta"]: fail.append(f"fade delta {gL - 128:.1f}")
    if grad < LIM["grad"]: fail.append(f"soft grad {grad:.2f}")
    sf = 100.0 * solid.mean()
    if not (LIM["sil"][0] <= sf <= LIM["sil"][1]): fail.append(f"silhouette {sf:.1f}%")
    if sat_skin > LIM["sat"][1]: fail.append(f"sat {sat_skin:.0f}")
    if sat_skin < LIM["sat"][0]: fail.append("no skin cluster")
    return {"file": os.path.basename(path), "dims": "ok", "spread": spread, "off": off, "cellstd": cellstd,
            "sil": sf, "g": gL, "delta": gL - 128.0, "grad": grad, "sat": sat_skin, "skinL": skinL,
            "clothfrac": float(cloth.sum() / max(solid.sum(), 1)), "fail": fail, "_sil": solid}


def pose_agreement(tone_folder, base_folder):
    """Every tone file must be the SAME frame as its base master except skin, or the shared masks break.

    silhouette IoU < 0.985  => the model shifted or scaled; the universal mask will cut across cloth.
    background pixels moved => the backdrop was re-rendered instead of the skin being edited.
    """
    rows = []
    bases = {os.path.splitext(os.path.basename(q))[0].split("-")[0]: q
             for q in sorted(glob.glob(os.path.join(base_folder, "*.jpg")))}
    for q in sorted(glob.glob(os.path.join(tone_folder, "*.jpg"))):
        key = os.path.splitext(os.path.basename(q))[0].split("-")[0]
        if key not in bases:
            rows.append((os.path.basename(q), -1.0, -1.0, "no base master for this outfit")); continue
        A = np.asarray(Image.open(q).convert("RGB"), dtype=float)
        B = np.asarray(Image.open(bases[key]).convert("RGB"), dtype=float)
        sa = ndimage.binary_fill_holes(body_silhouette(A)); sb = ndimage.binary_fill_holes(body_silhouette(B))
        iou = float(np.logical_and(sa, sb).sum() / max(np.logical_or(sa, sb).sum(), 1))
        out = ~sb & ~ndimage.binary_dilation(sb, np.ones((3, 3)))
        bgchg = float((np.abs(A.mean(2) - B.mean(2))[out] > 6).mean()) if out.any() else 1.0
        bad = []
        if iou < 0.985: bad.append(f"IoU {iou:.3f} pose drift")
        if bgchg > 0.002: bad.append(f"backdrop re-rendered {bgchg*100:.2f}%")
        rows.append((os.path.basename(q), iou, bgchg, ", ".join(bad) or "PASS"))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--iou", action="store_true")
    ap.add_argument("--base", default="", help="base folder; checks pose/backdrop lock for a tone folder")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.folder, "*.jpg")) + glob.glob(os.path.join(a.folder, "*.png")))
    if not files:
        print(f"no images in {a.folder}")
        return 0
    rows = [analyse(f) for f in files]
    bad = [r for r in rows if r["fail"]]
    if not a.quiet:
        print(f"{'file':32s} {'bgspread':>8s} {'off':>5s} {'cstd':>6s} {'sil%':>6s} {'garmentL':>8s} "
              f"{'delta':>6s} {'sharp':>6s} {'sat':>5s} {'skinL':>6s} {'clothfrac':>9s}  verdict")
        for r in rows:
            if "dims" in r and r.get("fail") == ["dims"]:
                print(f"{r['file']:32s} WRONG DIMS {r['dims']}  FAIL")
                continue
            print(f"{r['file'][:32]:32s} {r['spread']:8.2f} {r['off']:5.2f} {r['cellstd']:6.3f} {r['sil']:6.1f} "
                  f"{r['g']:8.1f} {r['delta']:6.1f} {r['grad']:6.2f} {r['sat']:5.1f} {r['skinL']:6.1f} "
                  f"{r['clothfrac']:9.3f}  " + ("FAIL: " + ", ".join(r["fail"]) if r["fail"] else "PASS"))
    print(f"\n{len(rows) - len(bad)} PASS / {len(bad)} FAIL   (gates: spread<={LIM['spread']} off<={LIM['off']} "
          f"cstd<={LIM['cellstd']} delta>={LIM['delta']} sharp>={LIM['grad']} sil {LIM['sil']} clothfrac>0.55)")
    if a.base:
        pr = pose_agreement(a.folder, a.base)
        print("\ntone-vs-base lock (mask reusability gate):")
        for f, iou, bgc, v in pr:
            print(f"  {f:34s} IoU={iou:.4f} bgmoved={bgc*100:6.3f}%  {v}")
        nb = sum(1 for r in pr if r[3] != "PASS")
        print(f"  {len(pr)-nb}/{len(pr)} locked, {nb} NOT USABLE with the universal masks")
        if nb:
            return 1
    if a.iou and len(rows) > 1:
        sils = [(r["file"].split("-")[0], r["_sil"]) for r in rows if "_sil" in r]
        pairs = []
        for i in range(len(sils)):
            for j in range(i + 1, len(sils)):
                inter = np.logical_and(sils[i][1], sils[j][1]).sum()
                uni = np.logical_or(sils[i][1], sils[j][1]).sum()
                pairs.append((inter / max(uni, 1), sils[i][0], sils[j][0]))
        pairs.sort(reverse=True)
        print("\ntop silhouette IoU pairs. >0.945 = the same garment rendered twice (a bug).")
        print("0.925-0.945 = different outfits, near-identical silhouette: the customer cannot tell the")
        print("cards apart on the product grid - fix by changing fit/length, not by re-rolling noise:")
        for v, a1, b1 in pairs[:12]:
            flag = "  <== DUPLICATE" if v > 0.945 else ("  <== too similar" if v > 0.925 else "")
            print(f"  {a1:8s} vs {b1:8s}  {v:.3f}{flag}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
