"""The colour chip strip for the six cards the shop actually sells.

Six chips, one per folder, in the order the picker should list them (pale to dark, with `as-shot`
where its own lightness puts it). Each colour is measured, not typed: median of the pixels inside
each outfit's skin region, averaged over the sample frames, read off the files that ship. That is
the whole reason this file exists - a swatch hand-copied from a palette drifts from the photos, and
then the customer picks a chip and gets a different face.

There is deliberately no "master" chip. `as-shot` is the master (32/32 files byte-identical to
base/), so a source column here would print the same colour twice and read as seven cards.
"""
import argparse
import json
import textwrap
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from mask_blue import LADDER, skin_region                       # noqa: E402
from mask_code import classify, roles_for                       # noqa: E402

# the picker order the shop asked for; as-shot sits where its lightness actually falls
ORDER = ["light-warm", "light-tan", "medium-brown", "as-shot", "deep", "ebony"]
NAMES = {"light-warm": "Light warm", "light-tan": "Light tan", "medium-brown": "Medium brown",
         "as-shot": "As shot", "deep": "Deep brown", "ebony": "Ebony"}
SAMPLE = ["M1", "M5", "M6", "W2", "W4", "W10", "W12", "W17"]   # faces + feet, men + women
W, H, HEAD, BAND = 246, 56, 56, 152


def measure(folder, slug, region):
    """Median colour of this folder's frame over the master's skin region (the frame's own ruler)."""
    return np.median(np.asarray(Image.open(os.path.join(ROOT, "template", folder, slug))
                                .convert("RGB"), dtype=float)[region], 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "template", "_qc", "skin-tones.png"))
    ap.add_argument("--order", default=",".join(ORDER), help="comma list of rung names")
    a = ap.parse_args()
    # mask_blue.LADDER is the rung -> (skinL, skinS) map the generator drives from; the prose per rung
    # lives in the same JSON, so read both from one source rather than half-trusting each.
    rung = json.load(open(os.path.join(HERE, "tone-ladder.json")))["tones"]
    order = [x.strip() for x in a.order.split(",") if x.strip()]
    missing = [t for t in order if t not in LADDER or t not in rung]
    if missing:
        print(f"FAIL: not rungs in tools/tone-ladder.json: {missing}")
        return 2
    man = json.load(open(os.path.join(ROOT, "template", "pieces.json")))
    cols = {t: [] for t in order}
    used = 0
    for o in man["outfits"]:
        if o["id"] not in SAMPLE:
            continue
        used += 1
        slug = o["image"].split("/")[-1]
        rgb = np.asarray(Image.open(os.path.join(ROOT, "template", "base", slug))
                         .convert("RGB"), dtype=float)
        codes = [c for c in ["rose", "blue", "green"] if c in roles_for(o).values()]
        lm, _, _ = classify(rgb, codes)
        avoid = np.where(lm > 0, 255, 0).astype(np.uint8)
        m = skin_region(rgb, avoid)
        for t in order:
            cols[t].append(measure(t, slug, m))
    if not used:
        print("FAIL: no sample outfits found")
        return 1

    sheet = Image.new("RGB", (len(order) * (W + 12) + 12, HEAD + BAND + 148), (24, 24, 27))
    d = ImageDraw.Draw(sheet)
    fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    fm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    d.text((12, 6), f"HueFit - the {len(order)} skin tones offered "
                    f"(measured on the {used} outfits, faces and feet)",
           fill=(246, 246, 250), font=fb)
    y = HEAD
    for i, t in enumerate(order):
        c = np.array(cols[t]).mean(0)
        c = tuple(int(round(v)) for v in c)
        x = 12 + i * (W + 12)
        d.rectangle([x, y, x + W, y + BAND], fill=c, outline=(64, 64, 70))
        d.text((x, y + BAND + 8), NAMES[t], fill=(242, 242, 246), font=fb)
        for j, ln in enumerate(textwrap.wrap(rung[t]["desc"], 29)[:3]):
            d.text((x, y + BAND + 34 + j * 17), ln, fill=(196, 196, 202), font=fs)
        d.text((x, y + BAND + 90), "#%02X%02X%02X" % c, fill=(150, 215, 255), font=fm)
        d.text((x, y + BAND + 110), f"lightness {np.mean(c):.0f}   warmth {int(max(c) - min(c))}",
               fill=(170, 180, 196), font=fs)
        note = "folder: base/ copied" if t == "as-shot" else f"folder: {t}/"
        d.text((x, y + BAND + 127), note, fill=(132, 142, 158), font=fs)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sheet.save(a.out)
    print(f"{a.out}  {sheet.width}x{sheet.height}  {len(order)} chips: {', '.join(order)}")
    for t in order:
        c = tuple(int(round(v)) for v in np.array(cols[t]).mean(0))
        print(f"  {t:13s} #{'%02X%02X%02X' % c}  lightness {np.mean(c):5.1f}  warmth {max(c) - min(c)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
