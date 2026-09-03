#!/usr/bin/env python3
"""Re-pin template/pieces.json against the files that actually exist on disk.

pieces.json is written by hand first (name, pieces, z-order) and then consumed
by three different mask builders, so its `status` fields go stale within one
run - and its `slug`/`image` fields can point at a filename that was never
generated (that silently hid W17 from every stage for a whole session). This
rewrites the image path and the per-piece status from what is on disk, and
prints anything that is still missing. It never deletes a piece definition.
"""
import glob
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TPL = os.path.join(ROOT, "template")


def main():
    path = os.path.join(TPL, "pieces.json")
    man = json.load(open(path))
    have = {os.path.basename(p) for p in glob.glob(os.path.join(TPL, "universal-masking", "*.png"))}
    total = done = 0
    fixed_paths = []
    incomplete = []
    for o in man["outfits"]:
        want = os.path.join(TPL, o["image"])
        if not os.path.exists(want):
            alt = sorted(glob.glob(os.path.join(TPL, "base", o["id"] + "-*.jpg")))
            if alt:
                o["image"] = os.path.relpath(alt[0], TPL)
                o["slug"] = os.path.basename(alt[0])[len(o["id"]) + 1:-4]
                fixed_paths.append(f"{o['id']}: image path re-pointed at {os.path.basename(alt[0])}")
        for p in o["pieces"]:
            total += 1
            png = f"{o['id']}-{p['piece']}-mask.png"
            if png in have:
                p["status"] = "built"
                done += 1
            else:
                p["status"] = "pending" if os.path.exists(os.path.join(TPL, o["image"])) else "no-base"
                incomplete.append((o["id"], p["piece"]))
        # group rollup, if the manifest carries one
        o["masks"] = sum(1 for p in o["pieces"] if p["status"] == "built")
    json.dump(man, open(path, "w"), indent=1)
    for m in fixed_paths:
        print("  fixed " + m)
    outfit_done = [o["id"] for o in man["outfits"] if all(p["status"] == "built" for p in o["pieces"])]
    print(f"{done}/{total} mask files exist; {len(outfit_done)}/32 outfits complete")
    if incomplete:
        byo = {}
        for oid, piece in incomplete:
            byo.setdefault(oid, []).append(piece)
        print("still missing: " + "; ".join(f"{k}({','.join(v)})" for k, v in sorted(byo.items())))
    # every shipped mask must be 768x1376 8-bit grey
    bad = [f for f in sorted(have)
           if Image.open(os.path.join(TPL, "universal-masking", f)).size != (768, 1376)
           or Image.open(os.path.join(TPL, "universal-masking", f)).mode not in ("L", "P", "1")]
    print(f"geometry check: {len(bad)} wrong-sized/non-grey mask(s)" + (f" -> {bad}" if bad else " - all 768x1376 greyscale"))
    return 0 if not incomplete else 1


if __name__ == "__main__":
    sys.exit(main())
