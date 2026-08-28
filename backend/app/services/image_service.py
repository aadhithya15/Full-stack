"""Outfit image URLs via Pollinations.ai - free, keyless.

The URL itself IS the image: Pollinations generates it on first load.

PROMPT DESIGN (research-based text-to-image best practices):
  - Subject FIRST (models weight early tokens most), quality tags trail.
  - Specific > vague: named garments, fabrics, jewellery.
  - Camera language for photorealism; trailing negative phrases.
  - PREFERRED PATH: the LLM writes a dedicated `image_prompt` per outfit;
    this builder is the fallback (mock mode / missing field).

TWO-LEVEL styling chosen by the user:
  outfit_culture:   tamil | indian | western | fusion | let-ai-decide
  outfit_formality: traditional | formal | casual | party | festive | let-ai-decide
The combination drives the model description and the scene.
"""
from __future__ import annotations

import random
import urllib.parse

BASE = "https://image.pollinations.ai/prompt/"

_QUALITY_TAIL = (
    "professional fashion editorial photography, shot on 85mm lens, sharp focus, "
    "realistic fabric texture and drape, natural skin, natural hands, "
    "soft studio lighting, elegant pose, clean background, photorealistic, "
    "no text, no watermark, no logo, no blur, no deformed hands"
)

# ---- Level 1: culture -> who the model is ----
_CULTURE_MODEL = {
    "tamil": {
        "female": "beautiful South Indian Tamil woman with dusky radiant skin",
        "male": "handsome South Indian Tamil man",
    },
    "western": {
        "female": "elegant woman",
        "male": "stylish man",
    },
    "fusion": {
        "female": "fashionable South Indian woman",
        "male": "fashionable South Indian man",
    },
}

# ---- Level 1 x Level 2: culture+formality -> attire flavour + scene ----
_FLAVOUR = {
    ("tamil", "traditional"): {
        "female": "wearing authentic Tamil traditional attire, Kanjivaram silk drape with contrast zari temple border, temple jewellery, jhumka earrings, fresh jasmine flowers in braided hair",
        "male": "wearing traditional Tamil veshti with silk shirt and angavastram over the shoulder",
        "scene": "elegant Chennai wedding hall with silk drapes and banana leaf decor",
    },
    ("tamil", "formal"): {
        "female": "wearing an elegant South Indian office-appropriate outfit, crisp handloom cotton saree or tailored salwar set with minimal gold jewellery",
        "male": "wearing a crisp formal shirt with tailored trousers, neat South Indian professional look",
        "scene": "modern Chennai office lobby with warm natural light",
    },
    ("tamil", "casual"): {
        "female": "wearing a comfortable everyday South Indian outfit, soft cotton kurti with leggings or casual Chettinad cotton saree, simple stud earrings",
        "male": "wearing a casual cotton shirt with veshti or comfortable trousers, relaxed South Indian everyday look",
        "scene": "sunlit Chennai street cafe with plants",
    },
    ("tamil", "party"): {
        "female": "wearing a glamorous modern South Indian party outfit, silk blend with contemporary cut, statement jhumkas, sleek hair with jasmine accent",
        "male": "wearing a stylish silk-blend shirt with tailored trousers, modern South Indian evening look",
        "scene": "upscale Chennai rooftop lounge at night with warm lights",
    },
    ("tamil", "festive"): {
        "female": "wearing bright festive Tamil attire, rich pattu pavadai or silk saree in celebratory colours, gold temple jewellery, flowers in hair",
        "male": "wearing festive silk veshti and kurta with angavastram",
        "scene": "decorated Tamil festival setting with kolam patterns and oil lamps",
    },
    ("western", "traditional"): {
        "female": "wearing a classic timeless western outfit with refined tailoring",
        "male": "wearing a classic tailored western suit",
        "scene": "elegant classic interior with soft window light",
    },
    ("western", "formal"): {
        "female": "wearing polished western business attire, tailored blazer and trousers or sheath dress",
        "male": "wearing a sharp business suit with tie",
        "scene": "modern corporate office with glass and natural light",
    },
    ("western", "casual"): {
        "female": "wearing relaxed western casual wear, well-fitted jeans and stylish top",
        "male": "wearing smart-casual western wear, chinos and a crisp shirt",
        "scene": "trendy urban coffee shop",
    },
    ("western", "party"): {
        "female": "wearing a chic western evening outfit, cocktail dress with elegant heels",
        "male": "wearing a fashionable western evening look, blazer over fitted shirt",
        "scene": "stylish nightclub lounge with ambient lighting",
    },
    ("western", "festive"): {
        "female": "wearing a festive western outfit with celebratory sparkle",
        "male": "wearing a festive smart western outfit",
        "scene": "celebration venue with string lights",
    },
    ("fusion", "traditional"): {
        "female": "wearing an indo-western fusion outfit, traditional Indian fabric in a modern silhouette",
        "male": "wearing an indo-western fusion outfit blending ethnic fabric with modern cut",
        "scene": "chic urban venue with traditional Indian accents",
    },
    ("fusion", "formal"): {
        "female": "wearing a fusion formal outfit, structured western cut with Indian textile detailing",
        "male": "wearing a fusion formal look, Nehru-collar blazer with tailored trousers",
        "scene": "contemporary boutique hotel lobby",
    },
    ("fusion", "casual"): {
        "female": "wearing casual fusion wear, kurta over jeans with modern accessories",
        "male": "wearing casual fusion wear, short kurta with denims",
        "scene": "artsy urban cafe with warm tones",
    },
    ("fusion", "party"): {
        "female": "wearing a party fusion outfit, saree draped with a belt or dhoti pants with crop top",
        "male": "wearing a party fusion outfit, asymmetric kurta with sleek trousers",
        "scene": "rooftop party venue at golden hour",
    },
    ("fusion", "festive"): {
        "female": "wearing festive fusion attire, traditional weave in a contemporary silhouette with statement jewellery",
        "male": "wearing festive fusion attire with embroidered modern jacket",
        "scene": "festive urban celebration with lanterns",
    },
}

_DEFAULT_CULTURE = "tamil"   # user base is Tamil Nadu
_DEFAULT_FORMALITY = "traditional"


def _flavour(culture: str, formality: str, gender: str) -> tuple[str, str, str]:
    c = culture if culture in _CULTURE_MODEL else _DEFAULT_CULTURE
    f = formality if formality != "let-ai-decide" else _DEFAULT_FORMALITY
    combo = _FLAVOUR.get((c, f)) or _FLAVOUR[(_DEFAULT_CULTURE, _DEFAULT_FORMALITY)]

    who = _CULTURE_MODEL[c].get("female" if gender == "female" else "male")
    if gender not in ("male", "female"):
        who = "fashion model"
    attire = combo.get("female" if gender == "female" else "male")
    return who, attire, combo["scene"]


def _age_phrase(age: int | None, gender: str) -> str:
    """Age descriptor for the image model - drives visible age in the photo.

    User base is 14-45 (validated at the route)."""
    if not age:
        return ""
    who = "woman" if gender == "female" else "man" if gender == "male" else "person"
    if age < 18:
        teen = "girl" if gender == "female" else "boy" if gender == "male" else "teenager"
        return f"teenage {teen} around {age} years old, youthful modest styling, "
    if age < 24:
        return f"young {who} in their early twenties, "
    if age < 28:
        return f"young {who} in their mid twenties, "
    if age < 31:
        return f"stylish {who} in their late twenties, "
    if age < 38:
        return f"stylish {who} in their thirties, "
    if age < 40:
        return f"confident {who} in their late thirties, "
    return f"confident elegant {who} in their early forties, "


def outfit_image_url(
    outfit_name: str,
    description: str,
    colors: list[dict],
    gender: str,
    occasion: str,
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    age: int | None = None,
    llm_image_prompt: str = "",
) -> str:
    """Build the Pollinations URL.

    Preferred: the LLM's own detailed image prompt. Fallback: constructed
    prompt using the culture x formality flavour matrix.
    """
    llm_image_prompt = (llm_image_prompt or "").strip()
    if llm_image_prompt:
        prompt = f"{llm_image_prompt[:600]}, {_QUALITY_TAIL}"
    else:
        color_names = ", ".join(c.get("name", "") for c in colors[:3] if c.get("name"))
        who, attire, scene = _flavour(outfit_culture, outfit_formality, gender)
        age_part = _age_phrase(age, gender)
        prompt = (
            f"full body photograph of {age_part}{who}, {attire}, "
            f"outfit: {outfit_name}: {description[:200]}, "
            f"colour palette {color_names}, "
            f"at a {occasion} event, {scene}, "
            f"{_QUALITY_TAIL}"
        )

    seed = random.randint(1, 10_000_000)
    return (
        BASE
        + urllib.parse.quote(prompt)
        + f"?width=1024&height=1365&nologo=true&enhance=true&seed={seed}"
    )
