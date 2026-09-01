"""Visual demo of the recolour engine (T2).

    python scripts/demo_recolor.py

Loads the sample saree template, recolours it to the strategy document's
example colours (maroon / emerald / royal blue), and writes a side-by-side
strip to recolor_demo.jpg. Open the file and judge with your eyes.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from app.services.recolor_service import recolor_garment

tpl_path = Path("templates/sample/saree_f_01.jpg")
mask_path = Path("templates/sample/saree_f_01_mask.png")
if not tpl_path.exists():
    sys.exit("Run  python scripts/make_sample_template.py  first")

tpl = Image.open(tpl_path)
mask = Image.open(mask_path)

colors = [("maroon", "#800000"), ("emerald", "#0F7B4D"), ("royal blue", "#2B4C9B")]
strip = Image.new("RGB", (tpl.width * 4, tpl.height), (255, 255, 255))
strip.paste(tpl, (0, 0))

for i, (name, hexc) in enumerate(colors, start=1):
    t0 = time.time()
    out = recolor_garment(tpl, mask, hexc)
    print(f"{name:12} {hexc}   {(time.time()-t0)*1000:.0f}ms")
    strip.paste(out, (tpl.width * i, 0))

strip.save("recolor_demo.jpg", quality=90)
print("saved: recolor_demo.jpg  (original | maroon | emerald | royal blue)")
