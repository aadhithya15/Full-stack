"""Generate a sample template + mask pair for pipeline testing.

    python scripts/make_sample_template.py

Creates templates/sample/ with:
  saree_f_01.jpg, saree_f_01_mask.png  (garment = draped saree region)
  kurta_m_01.jpg, kurta_m_01_mask.png
  templates.csv

These are SYNTHETIC stand-ins so upload (T1) and recolouring (T2) can be
verified end-to-end today. Replace with the design team's real photo
templates + hand-made masks when they arrive - same filenames pattern.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

out = Path("templates/sample")
out.mkdir(parents=True, exist_ok=True)

W, H = 600, 900


def scene(garment_color, skin=(224, 172, 138), bg=(240, 238, 233)):
    img = Image.new("RGB", (W, H), bg)
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    dm = ImageDraw.Draw(mask)

    # head + neck (skin - NOT in mask)
    d.ellipse([250, 60, 350, 175], fill=skin)
    d.rectangle([283, 165, 317, 205], fill=skin)
    # arms (skin)
    d.polygon([(200, 250), (165, 470), (200, 475), (235, 262)], fill=skin)
    d.polygon([(400, 250), (435, 470), (400, 475), (365, 262)], fill=skin)

    # garment: draped torso + long flowing skirt (IN mask)
    body = [(215, 210), (385, 210), (420, 420), (445, 860), (155, 860), (180, 420)]
    d.polygon(body, fill=garment_color)
    dm.polygon(body, fill=255)
    # pallu-like diagonal drape over shoulder (in mask)
    shade = tuple(max(0, c - 25) for c in garment_color)
    drape = [(215, 210), (280, 210), (200, 620), (160, 600)]
    d.polygon(drape, fill=shade)
    dm.polygon(drape, fill=255)

    # fabric texture: subtle fold lines inside garment only
    for x in range(190, 440, 26):
        line_c = tuple(max(0, c - 14) for c in garment_color)
        d.line([(x, 260), (x - 18, 850)], fill=line_c, width=2)
    # feet hint (skin, below garment - not in mask)
    d.rectangle([250, 862, 290, 895], fill=skin)
    d.rectangle([320, 862, 360, 895], fill=skin)

    # soften image slightly (masks stay hard-edged)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    return img, mask


saree, saree_mask = scene((151, 57, 34))       # maroon saree
saree.save(out / "saree_f_01.jpg", quality=90)
saree_mask.save(out / "saree_f_01_mask.png")

kurta, kurta_mask = scene((238, 231, 214))     # cream kurta
kurta.save(out / "kurta_m_01.jpg", quality=90)
kurta_mask.save(out / "kurta_m_01_mask.png")

(out / "templates.csv").write_text(
    "template_code,dress_type,gender,culture,style_tags,base_hue_family,"
    "image_file,mask_file,notes\n"
    "saree_f_01,saree,female,tamil,traditional;festive,maroon-red,"
    "saree_f_01.jpg,saree_f_01_mask.png,synthetic sample\n"
    "kurta_m_01,kurta-pajama,male,tamil,traditional,white-cream,"
    "kurta_m_01.jpg,kurta_m_01_mask.png,synthetic sample\n"
)
print(f"sample templates written to {out}")
