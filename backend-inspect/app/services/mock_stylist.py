"""Mock recommendation generator - used while AI keys are placeholders.

Produces realistic, VARIED outfits (not one fixed list) so the frontend
and demo behave like the real thing:
  - respects occasion, gender, style preference and budget,
  - honours the exclude list (Generate More works in mock mode),
  - randomises names/colour combos per call.

The response shape is IDENTICAL to what the real AI service returns in
Phase 5 - swapping in real keys changes content, not structure.
"""
from __future__ import annotations

import random

# --- building blocks -------------------------------------------------------

_COLORS = {
    "warm": [
        ("Emerald Green", "#0F7B4D"), ("Mustard Yellow", "#D4A017"),
        ("Rust Orange", "#B7410E"), ("Antique Gold", "#C9A24B"),
        ("Deep Maroon", "#6E1423"), ("Coral Pink", "#E86A5B"),
        ("Olive Green", "#6B8E23"), ("Terracotta", "#C1683C"),
    ],
    "cool": [
        ("Royal Blue", "#2B4C9B"), ("Lavender", "#9B7FC7"),
        ("Emerald Green", "#0F7B4D"), ("Silver Grey", "#A8B2BD"),
        ("Berry Pink", "#B23A64"), ("Teal", "#0F7B7B"),
        ("Icy Blue", "#A7C7E7"), ("Plum", "#66334D"),
    ],
    "neutral": [
        ("Dusty Rose", "#C48793"), ("Sage Green", "#8FA98F"),
        ("Navy Blue", "#1F3554"), ("Ivory", "#F4F0E5"),
        ("Charcoal", "#3C3C3C"), ("Soft Peach", "#EFB796"),
        ("Burgundy", "#701C2E"), ("Slate Blue", "#5D6E9E"),
    ],
}

_AVOID = {
    "warm": [("Ash Grey", "#9E9E9E"), ("Neon Yellow", "#E8F542"), ("Icy Pastel Blue", "#CFE8F7")],
    "cool": [("Orange", "#E8720C"), ("Mustard", "#D4A017"), ("Camel Brown", "#A9743A")],
    "neutral": [("Neon Green", "#39FF14"), ("Fluorescent Pink", "#FF5FD2")],
}

_TRADITIONAL_F = ["Silk Anarkali", "Banarasi Saree", "Chikankari Kurta Set", "Lehenga Choli", "Kanjivaram Saree", "Sharara Set", "Cotton Handloom Saree", "Palazzo Kurta Set"]
_TRADITIONAL_M = ["Silk Kurta Pyjama", "Nehru Jacket Ensemble", "Linen Kurta Set", "Bandhgala Suit", "Pathani Suit", "Dhoti-Style Kurta"]
_WESTERN_F = ["Wrap Midi Dress", "Blazer & Palazzo Set", "A-Line Cocktail Dress", "High-Waist Trouser Set", "Satin Slip Dress", "Pleated Skirt & Blouse"]
_WESTERN_M = ["Slim-Fit Blazer Look", "Chinos & Oxford Shirt", "Double-Breasted Suit", "Polo & Tailored Trousers", "Linen Shirt & Slacks", "Turtleneck & Blazer"]

_ACCESSORIES_F = ["gold jhumkas", "kada bangle", "small potli bag", "pearl studs", "layered chain necklace", "silk clutch", "maang tikka", "statement ring", "delicate anklet"]
_ACCESSORIES_M = ["leather strap watch", "pocket square", "brooch pin", "beaded bracelet", "tie clip", "leather belt", "cufflinks"]
_FOOTWEAR_F = ["gold block-heel sandals", "nude pumps", "embellished juttis", "strappy flats", "kitten heels"]
_FOOTWEAR_M = ["tan brogues", "mojari shoes", "white leather sneakers", "black Oxford shoes", "suede loafers"]

_TIPS = [
    "Keep makeup warm-toned and let the outfit colour do the talking.",
    "Steam the outfit before wearing; crisp fabric photographs beautifully.",
    "One statement accessory only - keep the rest minimal.",
    "Choose breathable inner layers; comfort shows in confidence.",
    "Match metal tones (gold/silver) across all accessories.",
    "A soft updo or neat side part completes this silhouette well.",
]

_FABRIC_BY_WEATHER = {
    "hot": "breathable cotton", "humid": "airy linen",
    "rainy": "quick-dry blended fabric", "winter": "layered silk-wool blend",
    "any": "comfortable premium fabric",
}

_BUDGET_WORD = {"low": "budget-friendly", "medium": "mid-range", "premium": "designer-grade"}


def _undertone(skin_tone: str) -> str:
    t = (skin_tone or "").lower()
    if any(w in t for w in ("warm", "wheatish", "dusky", "olive", "golden", "brown", "deep")):
        return "warm"
    if any(w in t for w in ("cool", "fair", "pink", "pale", "light")):
        return "cool"
    return "neutral"


def _garment_details(base: str, female: bool, color1: str, color2: str, fabric: str) -> list[dict]:
    """Return concrete pieces so mock mode has the same shape as real AI."""
    look = base.lower()
    if female:
        if "saree" in look:
            return [
                {"item": "saree", "name": f"{color1} {fabric} saree", "colour": color1, "fabric": fabric},
                {"item": "blouse", "name": f"{color2} fitted blouse", "colour": color2, "fabric": fabric},
            ]
        if "lehenga" in look:
            return [
                {"item": "lehenga", "name": f"{color1} embroidered lehenga", "colour": color1, "fabric": fabric},
                {"item": "choli", "name": f"{color2} structured choli", "colour": color2, "fabric": fabric},
                {"item": "dupatta", "name": f"{color2} draped dupatta", "colour": color2, "fabric": fabric},
            ]
        if "kurta" in look or "palazzo" in look or "sharara" in look:
            return [
                {"item": "kurta", "name": f"{color1} {fabric} kurta", "colour": color1, "fabric": fabric},
                {"item": "bottom", "name": f"{color2} tailored palazzo trousers", "colour": color2, "fabric": fabric},
            ]
        return [
            {"item": "dress", "name": f"{color1} {look}", "colour": color1, "fabric": fabric},
            {"item": "layer", "name": f"{color2} light styling layer", "colour": color2, "fabric": fabric},
        ]

    if any(word in look for word in ("blazer", "suit", "bandhgala")):
        return [
            {"item": "shirt", "name": f"{color2} tailored shirt", "colour": color2, "fabric": fabric},
            {"item": "trousers", "name": f"{color1} straight-fit trousers", "colour": color1, "fabric": fabric},
            {"item": "blazer", "name": f"{color1} structured blazer", "colour": color1, "fabric": fabric},
        ]
    if any(word in look for word in ("kurta", "pathani", "dhoti")):
        return [
            {"item": "kurta", "name": f"{color1} {fabric} kurta", "colour": color1, "fabric": fabric},
            {"item": "bottom", "name": f"{color2} relaxed trousers", "colour": color2, "fabric": fabric},
        ]
    return [
        {"item": "shirt", "name": f"{color1} {fabric} shirt", "colour": color1, "fabric": fabric},
        {"item": "trousers", "name": f"{color2} tailored trousers", "colour": color2, "fabric": fabric},
    ]


def generate_mock_recommendations(
    skin_tone: str,
    occasion: str,
    gender: str,
    style_preference: str,
    budget: str,
    season_weather: str,
    dress_type: str = "let-ai-decide",
    preferred_material: str = "let-ai-decide",
    language: str = "en",
    count: int = 4,
    exclude: list[str] | None = None,
) -> tuple[str, list[dict]]:
    """Returns (detected_skin_tone_label, list of recommendation dicts)."""
    exclude = exclude or []
    tone = _undertone(skin_tone)
    palette = _COLORS[tone][:]
    random.shuffle(palette)

    female = gender == "female"
    if style_preference == "traditional":
        pool = _TRADITIONAL_F if female else _TRADITIONAL_M
    elif style_preference in ("western", "formal", "casual"):
        pool = _WESTERN_F if female else _WESTERN_M
    else:  # any -> mix both directions
        pool = (_TRADITIONAL_F + _WESTERN_F) if female else (_TRADITIONAL_M + _WESTERN_M)

    selected_type = (dress_type or "").strip().lower()
    if selected_type and selected_type not in {"any", "let-ai-decide"}:
        pool = [selected_type.replace("-", " ").title()]

    excluded_lower = {e.strip().lower() for e in exclude}
    selected_material = (preferred_material or "").strip().lower()
    fabric = (
        selected_material.replace("-", " ").title()
        if selected_material and selected_material not in {"any", "let-ai-decide"}
        else _FABRIC_BY_WEATHER.get(season_weather, _FABRIC_BY_WEATHER["any"])
    )
    budget_word = _BUDGET_WORD.get(budget, "mid-range")

    recos: list[dict] = []
    attempts = 0
    while len(recos) < count and attempts < 120:
        attempts += 1
        base = random.choice(pool)
        # After many failed attempts (heavy exclusion lists), start shifting
        # the colour pairing so new unique names keep appearing.
        shift = attempts // 20
        color1, hex1 = palette[(len(recos) * 2 + shift) % len(palette)]
        color2, hex2 = palette[(len(recos) * 2 + 1 + shift) % len(palette)]
        name = f"{color1} {base}"
        if attempts > 80:
            # Last resort: guarantee uniqueness with a style variant suffix.
            variant = random.choice(["Reimagined", "Modern Edit", "Signature Cut", "Festive Edit"])
            name = f"{color1} {base} ({variant})"
        if name.lower() in excluded_lower or any(r["outfit_name"] == name for r in recos):
            continue

        category = (
            "traditional" if base in _TRADITIONAL_F + _TRADITIONAL_M or any(word in base.lower() for word in ("saree", "lehenga", "kurta", "sherwani", "dhoti", "anarkali", "sharara", "nehru")) else "western"
        )
        accessories = random.sample(_ACCESSORIES_F if female else _ACCESSORIES_M, 3)
        footwear = random.choice(_FOOTWEAR_F if female else _FOOTWEAR_M)

        recos.append(
            {
                "outfit_name": name,
                "category": category,
                "outfit_type": base,
                "materials": [fabric],
                "description": (
                    f"A {budget_word} {base.lower()} in {color1.lower()} with "
                    f"{color2.lower()} detailing, cut in {fabric} - styled for a "
                    f"{occasion} setting to flatter a {tone}-undertone complexion."
                ),
                "garments": _garment_details(base, female, color1, color2, fabric),
                "dress_colors": [
                    {"name": color1, "hex": hex1},
                    {"name": color2, "hex": hex2},
                ],
                "accessories": accessories,
                "footwear": footwear,
                "styling_tips": random.choice(_TIPS),
                "avoid_colors": [
                    {"name": n, "hex": h} for n, h in random.sample(_AVOID[tone], 2)
                ],
                "match_score": random.randint(82, 97),
                "is_mock": True,
            }
        )

    detected = f"{tone} undertone ({skin_tone.strip()})" if skin_tone else f"{tone} undertone"
    return detected, recos
