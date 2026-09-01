"""Phase V2-2 LIVE verification - CLIP on this machine.

Run (first time downloads the ~350MB model once):

    python check_clip.py

Verifies: model loads, text and image embedding work, dimensions are 512,
and the MAP actually behaves (matching text lands nearer the matching
image than a mismatched one). Then times both operations.
"""
from __future__ import annotations

import sys
import time

OK = "  [OK]  "
FAIL = "  [FAIL]"


def main() -> int:
    print("HueFit v2 - CLIP check (first run downloads ~350MB once)")
    print("=" * 56)

    try:
        from PIL import Image

        from app.services.clip_service import embed_image, embed_text, model_info
    except Exception as e:
        print(f"{FAIL} import failed - did you install requirements? {e}")
        return 1

    info = model_info()
    print(f"        model: {info['model']} / {info['pretrained']}")

    # 1) load + text embed
    t0 = time.time()
    try:
        vec = embed_text("a maroon silk saree with gold border")
    except Exception as e:
        print(f"{FAIL} text embedding failed: {str(e)[:140]}")
        return 1
    load_and_first = time.time() - t0
    if len(vec) != 512:
        print(f"{FAIL} expected 512 dims, got {len(vec)}")
        return 1
    print(f"{OK} text -> 512 coordinates (load + first call: {load_and_first:.1f}s)")

    # 2) image embed
    maroon = Image.new("RGB", (300, 400), (151, 57, 34))
    blue = Image.new("RGB", (300, 400), (60, 90, 160))
    try:
        v_maroon = embed_image(maroon)
        v_blue = embed_image(blue)
    except Exception as e:
        print(f"{FAIL} image embedding failed: {str(e)[:140]}")
        return 1
    print(f"{OK} image -> 512 coordinates")

    # 3) the map behaves: maroon text nearer maroon image
    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    t_maroon = embed_text("maroon red fabric")
    sim_match = dot(t_maroon, v_maroon)
    sim_off = dot(t_maroon, v_blue)
    if sim_match > sim_off:
        print(f"{OK} map semantics OK (match {sim_match:.3f} > mismatch {sim_off:.3f})")
    else:
        print(f"{FAIL} map semantics broken ({sim_match:.3f} <= {sim_off:.3f})")
        return 1

    # 4) speed
    t0 = time.time()
    for _ in range(5):
        embed_text("modern fusion kurta set, minimal warm palette")
    txt_ms = (time.time() - t0) / 5 * 1000
    t0 = time.time()
    embed_image(maroon)
    img_ms = (time.time() - t0) * 1000
    print(f"{OK} speed: text {txt_ms:.0f}ms | image {img_ms:.0f}ms (plain CPU)")

    print("=" * 56)
    print("All checks passed - CLIP is ready on this machine.")
    print("Next: python scripts/index_catalogue.py catalogue/starter --dry-run")
    print("Then without --dry-run to upload the starter catalogue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
