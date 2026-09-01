"""Generate the 20-product SAMPLE starter catalogue (synthetic swatch images).

Run once:  python scripts/make_sample_catalogue.py
Creates:   catalogue/starter/products.csv + catalogue/starter/images/p0NN.jpg

These are clearly-marked SAMPLE images so the whole pipeline can be built
and demoed before any real product photos exist. Replace with real photos
by editing the CSV and dropping files into images/.
"""
from pathlib import Path
import csv

from PIL import Image, ImageDraw

items = [
    ("SAMPLE Maroon Silk Saree", "female", "saree", "tamil", "festive;wedding", 4999, (151,57,34), "maroon-red", "silk;zari;traditional"),
    ("SAMPLE Gold Zari Pattu Saree", "female", "saree", "tamil", "wedding", 8999, (201,162,75), "yellow-gold", "silk;zari;pattu"),
    ("SAMPLE Emerald Anarkali", "female", "anarkali", "tamil", "festive;party", 3499, (15,123,77), "green-olive", "flowing;embroidered"),
    ("SAMPLE Mustard Cotton Kurti Set", "female", "kurta-palazzo", "tamil", "casual-outing", 1299, (212,160,23), "yellow-gold", "cotton;everyday"),
    ("SAMPLE Teal Sharara Set", "female", "sharara", "tamil", "festive", 4299, (15,123,123), "teal-cyan", "flared;festive"),
    ("SAMPLE Terracotta Lehenga Choli", "female", "lehenga-choli", "tamil", "wedding;reception", 7499, (193,104,60), "orange-rust", "embellished"),
    ("SAMPLE Ivory Georgette Gown", "female", "gown", "western", "party;reception", 5999, (244,240,229), "white-cream", "evening;elegant"),
    ("SAMPLE Black Cocktail Midi Dress", "female", "midi-dress", "western", "party;date-night", 2799, (28,28,30), "black", "cocktail;sleek"),
    ("SAMPLE Dusty Rose Maxi Dress", "female", "maxi-dress", "western", "brunch;casual-outing", 2299, (196,135,147), "pink-magenta", "flowy;daywear"),
    ("SAMPLE Navy Blazer & Trousers (W)", "female", "blazer-trousers", "western", "office;interview", 3999, (31,53,84), "blue", "formal;tailored"),
    ("SAMPLE Denim Jeans & White Top", "female", "jeans-top", "western", "casual-outing;college-farewell", 1599, (90,110,150), "blue", "denim;casual"),
    ("SAMPLE Olive Fusion Dhoti Jumpsuit", "female", "jumpsuit", "fusion", "party", 3299, (107,142,35), "green-olive", "indo-western;modern"),
    ("SAMPLE Cream Silk Kurta Pajama", "male", "kurta-pajama", "tamil", "festive;religious-ceremony", 2499, (240,231,210), "white-cream", "silk;classic"),
    ("SAMPLE Gold-Border Veshti & Shirt", "male", "kurta-dhoti", "tamil", "wedding;pongal", 1999, (235,228,200), "white-cream", "veshti;angavastram;zari"),
    ("SAMPLE Maroon Velvet Sherwani", "male", "sherwani", "tamil", "wedding", 9999, (110,20,35), "maroon-red", "velvet;embroidered"),
    ("SAMPLE Charcoal Two-Piece Suit", "male", "two-piece-suit", "western", "office;business-meeting", 6499, (54,54,58), "black", "formal;slim-fit"),
    ("SAMPLE White Shirt & Beige Chinos", "male", "shirt-trousers", "western", "casual-outing;brunch", 1899, (222,206,180), "beige-brown", "smart-casual"),
    ("SAMPLE Navy Polo & Jeans", "male", "polo-jeans", "western", "casual-outing", 1499, (40,60,110), "blue", "casual;weekend"),
    ("SAMPLE Black Nehru Jacket Set", "male", "nehru-jacket", "fusion", "reception;festive", 3799, (25,25,28), "black", "bandh-collar;layered"),
    ("SAMPLE Rust Pathani Suit", "male", "pathani-suit", "tamil", "festive;eid", 2199, (183,65,14), "orange-rust", "relaxed;classic"),
]

out = Path("catalogue/starter")
(out / "images").mkdir(parents=True, exist_ok=True)
rows = []
for i, (title, gender, dtype, culture, occ, price, rgb, fam, tags) in enumerate(items, 1):
    fn = f"p{i:03}.jpg"
    img = Image.new("RGB", (600, 800), rgb)
    d = ImageDraw.Draw(img)
    for y in range(0, 800, 16):
        shade = tuple(min(255, max(0, c + (6 if (y // 16) % 2 else -6))) for c in rgb)
        d.rectangle([0, y, 600, y + 8], fill=shade)
    light = tuple(min(255, c + 35) for c in rgb)
    d.rectangle([60, 90, 540, 700], outline=light, width=6)
    d.text((70, 20), "SAMPLE PRODUCT", fill=light)
    d.text((70, 740), title[:40], fill=light)
    img.save(out / "images" / fn, quality=88)
    rows.append({
        "title": title, "gender": gender, "dress_type": dtype, "culture": culture,
        "occasions": occ, "price": price, "image_file": fn, "buy_url": "",
        "color_hex": "", "hue_family": fam, "tags": tags,
    })

with open(out / "products.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

print(f"sample catalogue created: {len(rows)} products in {out}")
