# ============================================================
# HueFit Backend - TAMIL STYLES + AGE 14-45 (complete, v2)
# ------------------------------------------------------------
# REPLACES huefit-styles-age-complete.ps1 (age band changed).
# Safe to run over ANY previous state (tamil-style-final applied
# or not) - every file is written in full.
#
# Age feature (band 14-45, the actual user base):
#   - /analyze accepts optional age; must be 14-45, else clean 400
#   - stored in analyses (migration 005 - REWRITTEN: replaces the
#     old 5-100 DB constraint with 14-45 if it exists)
#   - AI rules by band: 14-17 teens (playful, modest, NO mature
#     styling), 18-27 young adults (trendy, bold), 28-37 adults
#     (polished, refined), 38-45 mature adults (elegant, premium)
#   - LLM image_prompt must describe a model of the same age group
#   - image fallback adds age phrases ("teenage girl around 15",
#     "confident elegant woman in their early forties")
# Plus everything from before: tamil/western/fusion cultures,
# 5 formality levels, LLM-written image prompts, Tamil vocabulary,
# 15-combo fallback matrix. 81 tests.
#
# AFTER running:
#   1. pytest -q                     (expect 80 passed, 1 skipped)
#   2. Supabase SQL Editor -> run migrations/005_age.sql
#      (REQUIRED even if you ran the old 005 - constraint changed)
#
# Run inside backend-inspect:
#   powershell -ExecutionPolicy Bypass -File .\huefit-styles-age-14-45.ps1
# ============================================================

$ErrorActionPreference = "Stop"

# ----- app\services\style_options.py -----
$content = @'
"""Curated style catalog exposed to the frontend.

The catalog is intentionally broad but finite: it keeps the UI useful and
predictable while the AI can still return a custom garment when the user
chooses "other" or "let AI decide".
"""

OCCASIONS = [
    {"value": "office", "label": "Office"},
    {"value": "business-meeting", "label": "Business meeting"},
    {"value": "interview", "label": "Interview"},
    {"value": "wedding", "label": "Wedding"},
    {"value": "reception", "label": "Reception"},
    {"value": "engagement", "label": "Engagement"},
    {"value": "religious-ceremony", "label": "Religious ceremony"},
    {"value": "festival", "label": "Festival"},
    {"value": "pongal", "label": "Pongal"},
    {"value": "diwali", "label": "Diwali"},
    {"value": "eid", "label": "Eid"},
    {"value": "onam", "label": "Onam"},
    {"value": "navratri", "label": "Navratri"},
    {"value": "party", "label": "Party"},
    {"value": "birthday", "label": "Birthday"},
    {"value": "date-night", "label": "Date night"},
    {"value": "dinner", "label": "Dinner"},
    {"value": "brunch", "label": "Brunch"},
    {"value": "college-farewell", "label": "College farewell"},
    {"value": "graduation", "label": "Graduation"},
    {"value": "casual-outing", "label": "Casual outing"},
    {"value": "travel", "label": "Travel"},
    {"value": "beach", "label": "Beach day"},
    {"value": "summer-picnic", "label": "Summer picnic"},
    {"value": "farewell", "label": "Farewell"},
    {"value": "casual", "label": "Everyday casual"},
    {"value": "other", "label": "Other / let AI decide"},
]

DRESS_TYPES = {
    "female": [
        {"value": "saree", "label": "Saree"},
        {"value": "lehenga-choli", "label": "Lehenga choli"},
        {"value": "anarkali", "label": "Anarkali"},
        {"value": "salwar-suit", "label": "Salwar suit"},
        {"value": "kurta-palazzo", "label": "Kurta and palazzo"},
        {"value": "sharara", "label": "Sharara"},
        {"value": "gharara", "label": "Gharara"},
        {"value": "gown", "label": "Gown"},
        {"value": "maxi-dress", "label": "Maxi dress"},
        {"value": "midi-dress", "label": "Midi dress"},
        {"value": "jumpsuit", "label": "Jumpsuit"},
        {"value": "skirt-blouse", "label": "Skirt and blouse"},
        {"value": "blazer-trousers", "label": "Blazer and trousers"},
        {"value": "western-coord", "label": "Western co-ord"},
        {"value": "kaftan", "label": "Kaftan"},
        {"value": "jeans-top", "label": "Jeans and top"},
        {"value": "let-ai-decide", "label": "Let AI decide"},
    ],
    "male": [
        {"value": "shirt-trousers", "label": "Shirt and trousers"},
        {"value": "blazer-chinos", "label": "Blazer and chinos"},
        {"value": "two-piece-suit", "label": "Two-piece suit"},
        {"value": "three-piece-suit", "label": "Three-piece suit"},
        {"value": "tuxedo", "label": "Tuxedo"},
        {"value": "kurta-pajama", "label": "Kurta pajama"},
        {"value": "kurta-dhoti", "label": "Kurta and dhoti"},
        {"value": "nehru-jacket", "label": "Nehru jacket"},
        {"value": "sherwani", "label": "Sherwani"},
        {"value": "bandhgala", "label": "Bandhgala"},
        {"value": "pathani-suit", "label": "Pathani suit"},
        {"value": "polo-jeans", "label": "Polo and jeans"},
        {"value": "casual-coord", "label": "Casual co-ord"},
        {"value": "formal-shirt-pants", "label": "Formal shirt and pants"},
        {"value": "let-ai-decide", "label": "Let AI decide"},
    ],
    "neutral": [
        {"value": "tailored-separates", "label": "Tailored separates"},
        {"value": "coord-set", "label": "Co-ord set"},
        {"value": "jumpsuit", "label": "Jumpsuit"},
        {"value": "layered-outfit", "label": "Layered outfit"},
        {"value": "relaxed-casual", "label": "Relaxed casual set"},
        {"value": "minimal-formal", "label": "Minimal formal look"},
        {"value": "let-ai-decide", "label": "Let AI decide"},
    ],
}

MATERIALS = [
    {"value": "cotton", "label": "Cotton"},
    {"value": "linen", "label": "Linen"},
    {"value": "silk", "label": "Silk"},
    {"value": "raw-silk", "label": "Raw silk"},
    {"value": "wool", "label": "Wool"},
    {"value": "cashmere", "label": "Cashmere"},
    {"value": "velvet", "label": "Velvet"},
    {"value": "denim", "label": "Denim"},
    {"value": "leather", "label": "Leather"},
    {"value": "suede", "label": "Suede"},
    {"value": "tweed", "label": "Tweed"},
    {"value": "corduroy", "label": "Corduroy"},
    {"value": "chiffon", "label": "Chiffon"},
    {"value": "georgette", "label": "Georgette"},
    {"value": "organza", "label": "Organza"},
    {"value": "satin", "label": "Satin"},
    {"value": "taffeta", "label": "Taffeta"},
    {"value": "crepe", "label": "Crepe"},
    {"value": "brocade", "label": "Brocade"},
    {"value": "lace", "label": "Lace"},
    {"value": "jersey", "label": "Jersey"},
    {"value": "knit", "label": "Knit"},
    {"value": "fleece", "label": "Fleece"},
    {"value": "rayon", "label": "Rayon"},
    {"value": "viscose", "label": "Viscose"},
    {"value": "modal", "label": "Modal"},
    {"value": "lyocell", "label": "Lyocell"},
    {"value": "polyester", "label": "Polyester"},
    {"value": "nylon", "label": "Nylon"},
    {"value": "spandex", "label": "Spandex"},
    {"value": "canvas", "label": "Canvas"},
    {"value": "khadi", "label": "Khadi"},
    {"value": "handloom-cotton", "label": "Handloom cotton"},
    {"value": "banarasi-silk", "label": "Banarasi silk"},
    {"value": "kanjivaram-silk", "label": "Kanjivaram silk"},
    {"value": "chanderi", "label": "Chanderi"},
    {"value": "chikankari-cotton", "label": "Chikankari cotton"},
    {"value": "bamboo", "label": "Bamboo fabric"},
    {"value": "hemp", "label": "Hemp"},
    {"value": "let-ai-decide", "label": "Let AI decide"},
]

# Level 1: cultural direction of the outfit
OUTFIT_CULTURES = [
    {"value": "tamil", "label": "Tamil"},
    {"value": "western", "label": "Western"},
    {"value": "fusion", "label": "Tamil-western fusion"},
    {"value": "let-ai-decide", "label": "Let AI decide"},
]

# Level 2: the style/formality within that culture
OUTFIT_FORMALITIES = [
    {"value": "traditional", "label": "Traditional / ceremonial"},
    {"value": "formal", "label": "Formal / office"},
    {"value": "casual", "label": "Casual / everyday"},
    {"value": "party", "label": "Party / evening"},
    {"value": "festive", "label": "Festive"},
    {"value": "let-ai-decide", "label": "Let AI decide"},
]

OPTION_VALUES = {
    "outfit_cultures": {item["value"] for item in OUTFIT_CULTURES},
    "outfit_formalities": {item["value"] for item in OUTFIT_FORMALITIES},
    "occasions": {item["value"] for item in OCCASIONS},
    "materials": {item["value"] for item in MATERIALS},
    "dress_types": {gender: {item["value"] for item in items} for gender, items in DRESS_TYPES.items()},
}


def public_options() -> dict:
    return {
        "events": OCCASIONS,
        "dress_types": DRESS_TYPES,
        "materials": MATERIALS,
        "outfit_cultures": OUTFIT_CULTURES,
        "outfit_formalities": OUTFIT_FORMALITIES,
    }
'@
Set-Content -Path "app\services\style_options.py" -Value $content -Encoding UTF8
Write-Host "updated  app\services\style_options.py"

# ----- app\services\image_service.py -----
$content = @'
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
'@
Set-Content -Path "app\services\image_service.py" -Value $content -Encoding UTF8
Write-Host "updated  app\services\image_service.py"

# ----- app\services\real_stylist.py -----
$content = @'
"""Real AI recommendations - Gemini (primary) with Groq (fallback).

Both providers are called over plain HTTPS with `requests` (no heavy SDKs).
The LLM must return STRICT JSON matching our schema; we parse, validate,
normalize, and retry once per provider before falling back.

Flow:  gemini (2 attempts) -> groq (2 attempts) -> ApiError.ai_unavailable
"""
from __future__ import annotations

import json
import logging
import random
import re

import requests

from app.config import Config
from app.utils.errors import ApiError

log = logging.getLogger(__name__)

# Model preference order. If none of these exist for your key, we use the
# best available model from the provider's live model list (auto-discovery).
# Models that 404 on an actual call get blacklisted so the next attempt
# tries a different one.
GEMINI_PREFERRED = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
GROQ_PREFERRED = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "groq/compound",
    "groq/compound-mini",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Model ids that are not chat/text models - never pick these from a live list.
_NON_CHAT_HINTS = (
    "whisper", "tts", "guard", "orpheus", "embedding", "image",
    "lyria", "robotics", "computer-use", "deep-research", "allam",
    "antigravity", "banana", "clip",
)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_URL = GROQ_BASE + "/chat/completions"
LANGUAGE_NAMES = {"en": "English", "ta": "Tamil", "hi": "Hindi"}


_TRANSLATION_CACHE: dict[tuple[str, str], str] = {}
_TRANSLATE_MARKER = "<<<HUEFIT_FIELD_BREAK>>>"


def _translate_text(text: str, target: str) -> str:
    """Translate user-facing AI text with a keyless fallback for ta/hi.

    The prompt asks the model for native-language output first. This second
    pass protects the UI when a free model ignores that instruction. The
    Google Translate web endpoint is keyless and may itself be rate-limited;
    if it fails, the original AI text is kept rather than breaking analysis.
    """
    if target == "en" or not text:
        return text
    key = (target, text)
    if key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[key]
    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        translated = "".join(part[0] for part in data[0] if part and part[0]).strip()
        if translated:
            _TRANSLATION_CACHE[key] = translated
            return translated
    except Exception as exc:
        log.warning("free translation fallback failed (%s): %s", target, str(exc)[:100])
    return text


def _translate_batch(values: list[str], target: str) -> list[str]:
    """Translate several short values in one request to avoid many API calls."""
    if target == "en" or not values:
        return values
    joined = f" { _TRANSLATE_MARKER } ".join(values)
    translated = _translate_text(joined, target)
    parts = [part.strip() for part in translated.split(_TRANSLATE_MARKER)]
    if len(parts) == len(values):
        return parts
    # Some translation gateways add spaces around punctuation/markers. Try
    # one tolerant split before preserving the original values.
    normalized = translated.replace("<<< HUEFIT_FIELD_BREAK >>>", _TRANSLATE_MARKER)
    parts = [part.strip() for part in normalized.split(_TRANSLATE_MARKER)]
    return parts if len(parts) == len(values) else values


def _localize_recommendation(recommendation: dict, language: str) -> dict:
    """Translate display strings while preserving machine-readable fields."""
    if language == "en":
        return recommendation

    fields: list[str] = [
        str(recommendation.get("outfit_name", "")),
        str(recommendation.get("description", "")),
    ]
    materials = [str(value) for value in recommendation.get("materials", [])]
    fields.extend(materials)

    garments = recommendation.get("garments", [])
    garment_name_indexes: list[tuple[dict, str]] = []
    for garment in garments:
        if isinstance(garment, dict):
            for key in ("name", "colour", "fabric"):
                if garment.get(key):
                    garment_name_indexes.append((garment, key))
                    fields.append(str(garment[key]))

    accessories = [str(value) for value in recommendation.get("accessories", [])]
    fields.extend(accessories)
    fields.append(str(recommendation.get("footwear", "")))
    fields.append(str(recommendation.get("styling_tips", "")))

    avoid = recommendation.get("avoid_colors", [])
    avoid_indexes: list[dict] = []
    for colour in avoid:
        if isinstance(colour, dict) and colour.get("name"):
            avoid_indexes.append(colour)
            fields.append(str(colour["name"]))

    translated = _translate_batch(fields, language)
    cursor = 0
    recommendation["outfit_name"] = translated[cursor]; cursor += 1
    recommendation["description"] = translated[cursor]; cursor += 1
    if materials:
        recommendation["materials"] = translated[cursor:cursor + len(materials)]
        cursor += len(materials)

    for garment, key in garment_name_indexes:
        garment[key] = translated[cursor]
        cursor += 1

    if accessories:
        recommendation["accessories"] = translated[cursor:cursor + len(accessories)]
        cursor += len(accessories)
    if recommendation.get("footwear"):
        recommendation["footwear"] = translated[cursor]
        cursor += 1
    if recommendation.get("styling_tips"):
        recommendation["styling_tips"] = translated[cursor]
        cursor += 1
    for colour in avoid_indexes:
        colour["name"] = translated[cursor]
        cursor += 1

    # Colour names are also user-facing. Translate them in a separate small
    # batch while leaving their hex values untouched.
    dress_colours = recommendation.get("dress_colors", [])
    colour_values = [str(c.get("name")) for c in dress_colours if isinstance(c, dict) and c.get("name")]
    translated_colours = _translate_batch(colour_values, language)
    colour_cursor = 0
    for colour in dress_colours:
        if isinstance(colour, dict) and colour.get("name"):
            colour["name"] = translated_colours[colour_cursor]
            colour_cursor += 1
    return recommendation

TIMEOUT = 45  # seconds per provider call

_MODEL_CACHE: dict[str, str] = {}  # provider -> chosen model (per process)
_BLACKLIST: dict[str, set] = {"gemini": set(), "groq": set()}  # models that 404ed


def _is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return not any(h in low for h in _NON_CHAT_HINTS)


def _pick_model(provider: str) -> str:
    """Choose a model: preferred if available, else best usable from live list.

    Blacklisted models (ones that 404ed on a real call) are skipped, so a
    stale entry in the provider's list API cannot wedge us permanently.
    """
    cached = _MODEL_CACHE.get(provider)
    if cached and cached not in _BLACKLIST[provider]:
        return cached

    available: list[str] = []
    preferred = GEMINI_PREFERRED if provider == "gemini" else GROQ_PREFERRED
    try:
        if provider == "gemini":
            r = requests.get(
                GEMINI_BASE + "/models",
                params={"key": Config.GEMINI_API_KEY, "pageSize": 50},
                timeout=20,
            )
            r.raise_for_status()
            available = [
                m["name"].split("/")[-1]
                for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
        else:
            r = requests.get(
                GROQ_BASE + "/models",
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                timeout=20,
            )
            r.raise_for_status()
            available = [m["id"] for m in r.json().get("data", [])]
    except Exception as exc:
        log.warning("model discovery failed for %s: %s", provider, str(exc)[:120])
        # Fall back to the first non-blacklisted preferred name.
        for name in preferred:
            if name not in _BLACKLIST[provider]:
                return name
        return preferred[0]

    usable = [
        m for m in available
        if _is_chat_model(m) and m not in _BLACKLIST[provider]
    ]

    chosen = next((m for m in preferred if m in usable), None)
    if chosen is None:
        # Prefer flash/instant-style cheap models from whatever IS usable.
        cheap = [m for m in usable if "flash" in m or "instant" in m or "mini" in m]
        pool = cheap or usable
        chosen = pool[0] if pool else preferred[0]

    _MODEL_CACHE[provider] = chosen
    log.info("AI model selected for %s: %s", provider, chosen)
    return chosen


def _blacklist_model(provider: str, model: str) -> None:
    _BLACKLIST[provider].add(model)
    _MODEL_CACHE.pop(provider, None)
    log.warning("model %s blacklisted for %s (404), will pick another", model, provider)

# Style direction seeds: injected randomly so two identical requests
# still take different creative directions (anti-repetition lever).
_DIRECTIONS = [
    "one look should be a classic timeless choice, one a modern fusion twist, and one a bold statement",
    "vary the silhouettes strongly: one flowing, one structured/tailored, one relaxed",
    "vary the fabrics strongly: one rich weave, one light breathable, one textured",
    "include one understated minimal look and one richly detailed look",
    "one outfit should be a safe crowd-pleaser and one should be adventurous",
]


def _prompt(
    skin_tone: str,
    occasion: str,
    gender: str,
    style_preference: str,
    budget: str,
    season_weather: str,
    dress_type: str,
    preferred_material: str,
    language: str,
    notes: str,
    count: int,
    exclude: list[str],
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    age: int | None = None,
) -> str:
    exclude_block = (
        "\nDo NOT suggest any outfit similar to these already-shown outfits: "
        + "; ".join(exclude[:40])
        if exclude
        else ""
    )
    notes_block = f"\nUser's extra request: {notes}" if notes else ""
    direction = random.choice(_DIRECTIONS)
    language_name = LANGUAGE_NAMES.get(language, "English")
    age_text = f"{age} years old" if age else "not specified (assume mid-20s)"

    return f"""You are an expert personal fashion stylist for Indian and global fashion.

Generate exactly {count} DIVERSE outfit recommendations for this person:
- Skin tone: {skin_tone}
- Occasion: {occasion}
- Gender: {gender}
- Style preference: {style_preference}
- Budget level: {budget} (low = affordable high-street, medium = mid-range, premium = designer-grade)
- Weather/season: {season_weather}
- Requested dress type: {dress_type}
- Preferred material: {preferred_material}
- Outfit culture choice: {outfit_culture}
- Outfit style level: {outfit_formality}
- Age: {age_text}
- Response language: {language_name}
{notes_block}{exclude_block}

Age rules (apply to EVERY outfit; users are 14-45):
- The outfit must be age-appropriate in silhouette, coverage, colour intensity
  and accessories for a {age_text} person.
- Teens (14-17): playful, modest, comfortable, youthful; pattu pavadai /
  davani (half-saree) / simple kurtis for Tamil looks; NO plunging necklines,
  NO heavy makeup descriptions, NO overly mature styling.
- Young adults (18-27): contemporary, trend-aware, can be bold and
  experimental; college/first-job energy.
- Adults (28-37): polished and stylish; modern but refined; workwear-ready
  sophistication with fashionable edges.
- Mature adults (38-45): elegant and confident; sophisticated colour stories;
  graceful tailored cuts; premium fabrics over flashy trends.
- The image_prompt MUST describe a model of the SAME age group so the
  generated photo visibly matches (e.g. "teenage girl around 15",
  "woman in her early 20s", "confident woman in her early 40s").

Outfit culture rules (level 1 - WHAT cultural direction):
- "tamil": authentic Tamil Nadu / South Indian clothing vocabulary. Women: Kanjivaram
  and other South Indian silk sarees, pattu pavadai, davani (half-saree), South Indian
  salwar styles, cotton kurtis. Men: veshti (dhoti), angavastram, jibba, formal shirts.
  Use regional fabrics and weaves (Kanjivaram, Chettinad cotton, Coimbatore cotton,
  Madurai Sungudi) and details (zari border, korvai, temple border, checks). Jewellery:
  temple jewellery, jhumkas, kolusu; jasmine (malli poo) for hair on traditional looks.
- "western": contemporary western fashion only, no ethnic elements.
- "fusion": Tamil-western blends (saree draped with a belt, kurta over jeans, dhoti
  pants with crop top, Nehru-collar blazer over veshti-style trousers) - keep the
  ethnic side SOUTH INDIAN in fabric and detail.
- "let-ai-decide": pick tamil or western based on the occasion; default to Tamil
  styling for traditional/festive occasions since the user base is Tamil Nadu.

Outfit style level rules (level 2 - HOW dressy, WITHIN the chosen culture):
- "traditional": ceremonial/classic garments of that culture (e.g. tamil+traditional =
  Kanjivaram saree or veshti-angavastram; western+traditional = classic tailored suit).
- "formal": office/business appropriate (tamil+formal = crisp cotton saree or tailored
  salwar, minimal jewellery; western+formal = business suit / sheath dress).
- "casual": everyday comfortable (tamil+casual = cotton kurti with leggings, casual
  Chettinad cotton saree, casual veshti; western+casual = jeans and smart top).
- "party": evening/glamorous (tamil+party = modern silk-blend with statement jhumkas;
  western+party = cocktail dress / sharp blazer look).
- "festive": celebration wear of that culture (tamil+festive = bright pattu pavadai,
  festive silk veshti; western+festive = sparkle details).
- "let-ai-decide": infer the right level from the occasion.
BOTH levels must be respected together: e.g. tamil+casual must NOT produce heavy
ceremonial Kanjivaram; western+formal must NOT produce ethnic wear.

Language rules: Keep JSON keys exactly as written in English. Write every user-facing
text value in {language_name}, including outfit names, descriptions, garment names,
materials, colour names, accessories, footwear, styling tips, avoid-colour names,
and the detected skin-tone description. Keep hex codes unchanged. The category and
item fields may remain short machine-readable English values if needed.

Diversity rules: each outfit must differ in silhouette, fabric AND colour direction; {direction}.

Colour rules: choose colours that genuinely flatter the given skin tone.
Also list colours this skin tone should avoid.

Weather rules: fabrics must suit the weather (breathable cotton/linen for hot or humid, layers for winter).

Respond with ONLY a valid JSON object, no markdown fences, no commentary, exactly this schema:
{{
  "detected_skin_tone": "<short description of the skin tone and undertone>",
  "recommendations": [
    {{
      "outfit_name": "<short distinctive name, max 8 words>",
      "category": "<traditional|western|formal|casual|fusion>",
      "outfit_type": "<the selected or AI-chosen dress type>",
      "materials": ["<material 1>", "<material 2>"],
      "description": "<2-3 sentence vivid description of the outfit and why it suits this person>",
      "garments": [
        {{"item": "<saree|blouse|dress|shirt|trousers|skirt|blazer|kurta|jacket|dupatta>", "name": "<specific garment name>", "colour": "<colour>", "fabric": "<fabric>"}}
      ],
      "dress_colors": [{{"name": "<colour name>", "hex": "<#RRGGBB>"}}, {{"name": "...", "hex": "..."}}],
      "accessories": ["<item 1>", "<item 2>", "<item 3>"],
      "footwear": "<specific footwear suggestion>",
      "styling_tips": "<one practical styling tip>",
      "avoid_colors": [{{"name": "<colour name>", "hex": "<#RRGGBB>"}}],
      "image_prompt": "<ALWAYS IN ENGLISH regardless of response language: one detailed text-to-image prompt for this exact outfit, 50-90 words, structured as: full body photograph of <model matching the gender AND age group, South Indian appearance for tamil styles>, wearing <every garment piece with its exact colour, fabric and detail e.g. 'emerald green Kanjivaram silk saree with gold zari temple border, mustard silk blouse'>, <hair and jewellery details>, <fitting venue e.g. Chennai wedding hall / minimal studio>. Be concrete and visual - name real garment parts, fabrics, jewellery; never write vague words like nice, beautiful, stylish alone>",
      "match_score": <integer 70-99>
    }}
  ]
}}"""


# ----------------------------------------------------------- provider calls


def _call_gemini(prompt: str) -> str:
    model = _pick_model("gemini")
    resp = requests.post(
        f"{GEMINI_BASE}/models/{model}:generateContent",
        params={"key": Config.GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.95,
                "responseMimeType": "application/json",
            },
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str) -> str:
    model = _pick_model("groq")
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
        json={
            "model": model,
            "temperature": 0.95,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You are a fashion stylist API that responds only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ------------------------------------------------------- parse and validate

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _clean_color_list(raw, fallback_name: str = "Neutral") -> list[dict]:
    out = []
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict) and c.get("name"):
                hex_val = str(c.get("hex", "")).strip()
                if not _HEX_RE.match(hex_val):
                    hex_val = "#888888"
                out.append({"name": str(c["name"])[:40], "hex": hex_val})
    if not out:
        out = [{"name": fallback_name, "hex": "#888888"}]
    return out[:4]


def _clean_garments(raw) -> list[dict]:
    """Normalize garment details while accepting colour/color and type/item."""
    out = []
    if isinstance(raw, list):
        for garment in raw:
            if not isinstance(garment, dict):
                continue
            item = str(garment.get("item") or garment.get("type") or garment.get("item_type") or "").strip()
            name = str(garment.get("name") or garment.get("description") or "").strip()
            colour = str(garment.get("colour") or garment.get("color") or "").strip()
            fabric = str(garment.get("fabric") or "").strip()
            if not item or not name:
                continue
            out.append({
                "item": item[:30],
                "name": name[:100],
                "colour": colour[:40],
                "fabric": fabric[:40],
            })
    return out[:8]


def _clean_materials(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(value).strip()[:50] for value in raw if str(value).strip()][:8]


def _validate(payload_text: str, count: int, language: str = "en") -> tuple[str, list[dict]]:
    data = json.loads(_strip_fences(payload_text))
    if not isinstance(data, dict):
        raise ValueError("top level is not an object")

    recos_raw = data.get("recommendations")
    if not isinstance(recos_raw, list) or not recos_raw:
        raise ValueError("no recommendations array")

    recos: list[dict] = []
    for r in recos_raw[:count]:
        if not isinstance(r, dict) or not r.get("outfit_name"):
            continue
        accessories = r.get("accessories")
        if not isinstance(accessories, list):
            accessories = []
        try:
            score = int(r.get("match_score", 85))
        except (TypeError, ValueError):
            score = 85
        recos.append(
            {
                "outfit_name": str(r["outfit_name"])[:80],
                "category": str(r.get("category", "any"))[:20].lower(),
                "outfit_type": str(r.get("outfit_type", ""))[:60],
                "materials": _clean_materials(r.get("materials")),
                "description": str(r.get("description", ""))[:600],
                "garments": _clean_garments(r.get("garments")),
                "dress_colors": _clean_color_list(r.get("dress_colors")),
                "accessories": [str(a)[:60] for a in accessories][:5],
                "footwear": str(r.get("footwear", ""))[:100],
                "styling_tips": str(r.get("styling_tips", ""))[:300],
                "avoid_colors": _clean_color_list(r.get("avoid_colors"), "None specific"),
                "match_score": max(1, min(score, 100)),
                "image_prompt": str(r.get("image_prompt", ""))[:700],
                "is_mock": False,
            }
        )

    if len(recos) < 3:
        raise ValueError(f"only {len(recos)} valid recommendations")

    detected = str(data.get("detected_skin_tone", ""))[:120] or "as described"
    if language != "en":
        detected = _translate_text(detected, language)
        recos = [_localize_recommendation(reco, language) for reco in recos]
    return detected, recos


# ------------------------------------------------------------------ public


def get_real_recommendations(
    skin_tone: str,
    occasion: str,
    gender: str,
    style_preference: str,
    budget: str,
    season_weather: str,
    dress_type: str,
    preferred_material: str,
    language: str,
    notes: str,
    count: int,
    exclude: list[str],
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    age: int | None = None,
) -> tuple[str, list[dict]]:
    prompt = _prompt(
        skin_tone, occasion, gender, style_preference,
        budget, season_weather, dress_type, preferred_material,
        language, notes, count, exclude, outfit_culture, outfit_formality, age,
    )

    providers = []
    if not Config.is_placeholder(Config.GEMINI_API_KEY):
        providers.append(("gemini", _call_gemini))
    if not Config.is_placeholder(Config.GROQ_API_KEY):
        providers.append(("groq", _call_groq))

    last_error = "no AI provider configured"
    for name, call in providers:
        for attempt in (1, 2, 3):
            try:
                raw = call(prompt)
                detected, recos = _validate(raw, count, language)
                log.info("AI provider=%s attempt=%d -> %d recommendations", name, attempt, len(recos))
                return detected, recos
            except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
                last_error = f"{name} attempt {attempt}: {type(exc).__name__}: {str(exc)[:120]}"
                log.warning("AI call failed - %s", last_error)
                # If the chosen model 404s, blacklist it so the next attempt
                # picks a DIFFERENT model instead of retrying the same one.
                if isinstance(exc, requests.HTTPError) and exc.response is not None \
                        and exc.response.status_code == 404:
                    bad = _MODEL_CACHE.get(name)
                    if bad:
                        _blacklist_model(name, bad)

    raise ApiError.ai_unavailable(
        "The AI stylist is temporarily unavailable, please try again in a moment"
    )
'@
Set-Content -Path "app\services\real_stylist.py" -Value $content -Encoding UTF8
Write-Host "updated  app\services\real_stylist.py"

# ----- app\services\ai_service.py -----
$content = @'
"""AI recommendation facade.

ONE public function: get_recommendations(...).
  - Mock mode (AI keys are placeholders): uses mock_stylist. Everything
    works end-to-end ? auth, DB, images ? with realistic varied content.
  - Real mode (Phase 5): calls Gemini (primary) / Groq (fallback) and
    parses strict JSON. Same return shape; routes never change.

Return: (detected_skin_tone: str, recommendations: list[dict])
Each recommendation dict has: outfit_name, category, description,
dress_colors, accessories, footwear, styling_tips, avoid_colors,
match_score, is_mock  ? image_url is added by the route (image_service).
"""
from __future__ import annotations

from app.config import Config
from app.services.mock_stylist import generate_mock_recommendations
from app.utils.errors import ApiError


def get_recommendations(
    skin_tone: str,
    occasion: str,
    gender: str,
    style_preference: str = "any",
    budget: str = "medium",
    season_weather: str = "any",
    dress_type: str = "let-ai-decide",
    preferred_material: str = "let-ai-decide",
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    age: int | None = None,
    language: str = "en",
    notes: str = "",
    count: int = 4,
    exclude: list[str] | None = None,
) -> tuple[str, list[dict]]:
    exclude = exclude or []

    if Config.ai_mock_mode():
        return generate_mock_recommendations(
            skin_tone=skin_tone,
            occasion=occasion,
            gender=gender,
            style_preference=style_preference,
            budget=budget,
            season_weather=season_weather,
            dress_type=dress_type,
            preferred_material=preferred_material,
            language=language,
            count=count,
            exclude=exclude,
        )

    # Real mode: Gemini (primary) -> Groq (fallback), strict JSON.
    from app.services.real_stylist import get_real_recommendations

    try:
        return get_real_recommendations(
            skin_tone=skin_tone,
            occasion=occasion,
            gender=gender,
            style_preference=style_preference,
            outfit_culture=outfit_culture,
            outfit_formality=outfit_formality,
            age=age,
            budget=budget,
            season_weather=season_weather,
            dress_type=dress_type,
            preferred_material=preferred_material,
            language=language,
            notes=notes,
            count=count,
            exclude=exclude,
        )
    except ApiError:
        raise
    except Exception:
        # Absolute last resort: never give the user a hard failure when the
        # mock stylist can still produce a usable answer.
        return generate_mock_recommendations(
            skin_tone=skin_tone,
            occasion=occasion,
            gender=gender,
            style_preference=style_preference,
            budget=budget,
            season_weather=season_weather,
            dress_type=dress_type,
            preferred_material=preferred_material,
            language=language,
            count=count,
            exclude=exclude,
        )
'@
Set-Content -Path "app\services\ai_service.py" -Value $content -Encoding UTF8
Write-Host "updated  app\services\ai_service.py"

# ----- app\routes\fashion_routes.py -----
$content = @'
"""Fashion endpoints - Phase 4: POST /api/fashion/analyze (+ history).

The analyze endpoint accepts multipart/form-data (photo optional in
Phase 4; the photo FIELD is accepted and stored, but skin-tone detection
from the photo arrives in Phase 6 - until then skin_tone_text is used,
or a sensible default if only a photo is sent).
"""
from __future__ import annotations

import json

from flask import Blueprint, g, jsonify, request

from app.db import queries
from app.middleware.auth_middleware import require_auth
from app.middleware.rate_limit import rate_limit
from app.services import ai_service
from app.services.image_service import outfit_image_url
from app.services.style_options import OPTION_VALUES, public_options
from app.utils.errors import ApiError

fashion_bp = Blueprint("fashion", __name__)

OCCASIONS = OPTION_VALUES["occasions"]
GENDERS = {"male", "female", "neutral"}
STYLES = {"traditional", "western", "formal", "casual", "any"}
BUDGETS = {"low", "medium", "premium"}
WEATHER = {"hot", "humid", "rainy", "winter", "any"}
LANGUAGES = {"en", "ta", "hi"}
ALLOWED_PHOTO_MIME = {"image/jpeg", "image/png", "image/webp"}


def _form(name: str, default: str = "") -> str:
    return (request.form.get(name) or default).strip()


def _enum(value: str, allowed: set[str], field: str, default: str | None = None) -> str:
    value = value.lower()
    if not value and default is not None:
        return default
    if value not in allowed:
        raise ApiError.invalid_input(
            f"Invalid {field} '{value}'. Allowed: {', '.join(sorted(allowed))}"
        )
    return value


@fashion_bp.get("/options")
def options():
    """Return the catalogue used by the analysis form."""
    return jsonify({"success": True, **public_options()})


@fashion_bp.post("/analyze")
@require_auth
@rate_limit("analyze", per_minute=8)
def analyze():
    user_id = g.user["id"]

    # The language saved in Profile controls the language of AI user-facing text.
    # If an old profile or a temporary DB issue has no language, English is safe.
    language = "en"
    try:
        profile = queries.get_profile(user_id) or {}
        language = profile.get("language") or "en"
    except Exception:
        pass
    if language not in LANGUAGES:
        language = "en"

    # ---------- 1) validate inputs ----------
    skin_tone_text = _form("skin_tone_text")
    photo = request.files.get("photo")

    if photo is not None and photo.filename:
        if photo.mimetype not in ALLOWED_PHOTO_MIME:
            raise ApiError.invalid_input("Photo must be JPEG, PNG or WebP")
        input_type = "photo"
    elif skin_tone_text:
        input_type = "text"
    else:
        raise ApiError.invalid_input("Provide a photo or a skin_tone_text description")

    occasion = _enum(_form("occasion"), OCCASIONS, "occasion")
    gender = _enum(_form("gender"), GENDERS, "gender", default="neutral")
    style_preference = _enum(_form("style_preference"), STYLES, "style_preference", default="any")
    budget = _enum(_form("budget"), BUDGETS, "budget", default="medium")
    season_weather = _enum(_form("season_weather"), WEATHER, "season_weather", default="any")

    dress_type = _form("dress_type", "let-ai-decide").lower()
    allowed_dress_types = OPTION_VALUES["dress_types"].get(gender, OPTION_VALUES["dress_types"]["neutral"])
    if dress_type not in allowed_dress_types:
        raise ApiError.invalid_input(f"Invalid dress_type '{dress_type}'")
    preferred_material = _form("preferred_material", "let-ai-decide").lower()
    if preferred_material not in OPTION_VALUES["materials"]:
        raise ApiError.invalid_input(f"Invalid preferred_material '{preferred_material}'")
    outfit_culture = _form("outfit_culture", "let-ai-decide").lower()
    if outfit_culture not in OPTION_VALUES["outfit_cultures"]:
        raise ApiError.invalid_input(f"Invalid outfit_culture '{outfit_culture}'")
    outfit_formality = _form("outfit_formality", "let-ai-decide").lower()
    if outfit_formality not in OPTION_VALUES["outfit_formalities"]:
        raise ApiError.invalid_input(f"Invalid outfit_formality '{outfit_formality}'")

    # Age: optional but strongly recommended - recommendations and images are
    # tuned to the person's life stage.
    age_raw = _form("age")
    age = None
    if age_raw:
        try:
            age = int(age_raw)
        except ValueError:
            raise ApiError.invalid_input("age must be a whole number")
        if age < 14 or age > 45:
            raise ApiError.invalid_input("age must be between 14 and 45")

    notes = _form("notes")[:300]

    try:
        count = int(_form("count", "4"))
    except ValueError:
        raise ApiError.invalid_input("count must be a number")
    count = max(3, min(count, 5))

    exclude_raw = _form("exclude")
    exclude: list[str] = []
    if exclude_raw:
        try:
            parsed = json.loads(exclude_raw)
            if isinstance(parsed, list):
                exclude = [str(x) for x in parsed][:40]
        except json.JSONDecodeError:
            raise ApiError.invalid_input("exclude must be a JSON array of outfit names")

    # Server-side anti-repetition (Phase 7): even if the frontend forgets to
    # send exclusions, we remember this user's recent outfits ourselves.
    # avoid_repeats=false disables it (useful if a user WANTS to re-see looks).
    avoid_repeats = _form("avoid_repeats", "true").lower() != "false"
    if avoid_repeats:
        try:
            recent = queries.list_past_outfit_names(user_id, limit=15)
        except Exception:
            recent = []  # history lookup must never break the analysis
        seen = {e.strip().lower() for e in exclude}
        for name in recent:
            if name.strip().lower() not in seen:
                exclude.append(name)
                seen.add(name.strip().lower())
        exclude = exclude[:40]

    # ---------- 2) photo: detect skin tone + store ----------
    photo_path = None
    detected_from_photo = None
    if input_type == "photo":
        photo_bytes = photo.read()

        from app.services.skin_tone_service import detect_skin_tone

        detected_from_photo = detect_skin_tone(photo_bytes, photo.mimetype)

        from app.services.storage_service import upload_photo

        try:
            photo_path = upload_photo(user_id, photo_bytes, photo.mimetype)
        except Exception:
            photo_path = None  # storage hiccup shouldn't kill the analysis

    # Photo detection wins; typed text is used as extra context / fallback.
    skin_tone_for_ai = detected_from_photo or skin_tone_text or "medium neutral"
    if detected_from_photo and skin_tone_text:
        skin_tone_for_ai = f"{detected_from_photo} (user says: {skin_tone_text})"

    # ---------- 3) get recommendations (mock now, real AI in Phase 5) ----------
    detected_skin_tone, recos = ai_service.get_recommendations(
        skin_tone=skin_tone_for_ai,
        occasion=occasion,
        gender=gender,
        style_preference=style_preference,
        budget=budget,
        season_weather=season_weather,
        dress_type=dress_type,
        preferred_material=preferred_material,
        outfit_culture=outfit_culture,
        outfit_formality=outfit_formality,
        age=age,
        notes=notes,
        count=count,
        exclude=exclude,
        language=language,
    )
    if not recos:
        raise ApiError.ai_unavailable("Could not generate recommendations, please try again")

    # ---------- 4) add outfit image URLs ----------
    for r in recos:
        r["image_url"] = outfit_image_url(
            r["outfit_name"], r["description"], r["dress_colors"], gender, occasion,
            outfit_culture=outfit_culture,
        outfit_formality=outfit_formality,
        age=age,
            llm_image_prompt=r.pop("image_prompt", ""),
        )

    # ---------- 5) persist ----------
    analysis = queries.insert_analysis(
        user_id,
        {
            "input_type": input_type,
            "skin_tone_input": skin_tone_text or None,
            "detected_skin_tone": detected_skin_tone,
            "photo_url": photo_path,
            "occasion": occasion,
            "gender": gender,
            "style_preference": style_preference,
            "budget": budget,
            "season_weather": season_weather,
            "dress_type": dress_type,
            "preferred_material": preferred_material,
            "age": age,
            "notes": notes or None,
        },
    )
    saved = queries.insert_recommendations(user_id, analysis["id"], recos)

    # ---------- 6) respond (API-CONTRACT.md shape) ----------
    is_mock = bool(recos and recos[0].get("is_mock"))
    return jsonify(
        {
            "success": True,
            "analysis_id": analysis["id"],
            "detected_skin_tone": detected_skin_tone,
            "mock": is_mock,
            "language": language,
            "recommendations": [
                {
                    "id": row["id"],
                    "outfit_name": row["outfit_name"],
                    "category": row["category"],
                    "outfit_type": row.get("outfit_type") or dress_type,
                    "description": row["description"],
                    "garments": row.get("garments") or [],
                    "materials": row.get("materials") or [g.get("fabric") for g in (row.get("garments") or []) if isinstance(g, dict) and g.get("fabric")],
                    "dress_colors": row["dress_colors"],
                    "accessories": row["accessories"],
                    "footwear": row["footwear"],
                    "styling_tips": row["styling_tips"],
                    "avoid_colors": row["avoid_colors"],
                    "image_url": row["image_url"],
                    "match_score": row["match_score"],
                }
                for row in saved
            ],
        }
    )


@fashion_bp.get("/history")
@require_auth
def history():
    analyses = queries.list_analyses(g.user["id"])
    return jsonify(
        {
            "success": True,
            "analyses": [
                {
                    "id": a["id"],
                    "occasion": a["occasion"],
                    "skin_tone": a.get("skin_tone_input") or a.get("detected_skin_tone"),
                    "created_at": a["created_at"],
                }
                for a in analyses
            ],
        }
    )


# --------------------------------------------------- saved looks (Phase 8)


@fashion_bp.post("/save")
@require_auth
@rate_limit("save", per_minute=30)
def save_look():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError.invalid_input("Request body must be JSON")

    recommendation_id = str(body.get("recommendation_id", "")).strip()
    if not recommendation_id:
        raise ApiError.invalid_input("recommendation_id is required")

    is_favourite = bool(body.get("is_favourite", False))

    # Ownership check: the recommendation must exist AND belong to this user.
    reco = queries.get_recommendation(g.user["id"], recommendation_id)
    if reco is None:
        raise ApiError.not_found("Recommendation not found")

    saved = queries.save_look(g.user["id"], recommendation_id, is_favourite)
    return jsonify({"success": True, "id": saved["id"]}), 201


@fashion_bp.get("/saved")
@require_auth
def list_saved():
    rows = queries.list_saved_looks(g.user["id"])
    return jsonify(
        {
            "success": True,
            "saved_looks": [
                {
                    "id": row["id"],
                    "is_favourite": row["is_favourite"],
                    "saved_at": row["saved_at"],
                    "recommendation": row.get("recommendation"),
                }
                for row in rows
            ],
        }
    )


@fashion_bp.patch("/saved/<saved_id>")
@require_auth
def update_saved(saved_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "is_favourite" not in body:
        raise ApiError.invalid_input("Body must be JSON with is_favourite")

    ok = queries.set_favourite(g.user["id"], saved_id, bool(body["is_favourite"]))
    if not ok:
        raise ApiError.not_found("Saved look not found")
    return jsonify({"success": True, "id": saved_id})


@fashion_bp.delete("/saved/<saved_id>")
@require_auth
def delete_saved(saved_id: str):
    ok = queries.delete_saved_look(g.user["id"], saved_id)
    if not ok:
        raise ApiError.not_found("Saved look not found")
    return jsonify({"success": True, "id": saved_id})
'@
Set-Content -Path "app\routes\fashion_routes.py" -Value $content -Encoding UTF8
Write-Host "updated  app\routes\fashion_routes.py"

# ----- tests\test_real_ai.py -----
$content = @'
"""Phase 5 tests - real AI plumbing with providers mocked (run offline)."""
import json
from unittest.mock import patch

import pytest

from app.services.real_stylist import _strip_fences, _validate, get_real_recommendations
from app.utils.errors import ApiError

GOOD_PAYLOAD = json.dumps(
    {
        "detected_skin_tone": "warm wheatish undertone",
        "recommendations": [
            {
                "outfit_name": f"Test Outfit {i}",
                "category": "traditional",
                "description": "A lovely outfit.",
                "dress_colors": [{"name": "Emerald", "hex": "#0F7B4D"}],
                "accessories": ["earrings", "clutch"],
                "footwear": "juttis",
                "styling_tips": "Keep it simple.",
                "avoid_colors": [{"name": "Grey", "hex": "#9E9E9E"}],
                "match_score": 90,
            }
            for i in range(3)
        ],
    }
)

ARGS = dict(
    skin_tone="wheatish", occasion="wedding", gender="female",
    style_preference="traditional", budget="medium", season_weather="hot",
    dress_type="let-ai-decide", preferred_material="let-ai-decide",
    language="en", notes="", count=3, exclude=[],
)


def test_strip_fences():
    fenced = "```json\n{\"a\": 1}\n```"
    assert json.loads(_strip_fences(fenced)) == {"a": 1}


def test_validate_good_payload():
    detected, recos = _validate(GOOD_PAYLOAD, 3)
    assert detected == "warm wheatish undertone"
    assert len(recos) == 3
    assert recos[0]["is_mock"] is False


def test_validate_fixes_bad_hex():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"][0]["dress_colors"][0]["hex"] = "greenish"
    _, recos = _validate(json.dumps(bad), 3)
    assert recos[0]["dress_colors"][0]["hex"] == "#888888"


def test_validate_rejects_too_few():
    bad = json.loads(GOOD_PAYLOAD)
    bad["recommendations"] = bad["recommendations"][:1]
    with pytest.raises(ValueError):
        _validate(json.dumps(bad), 3)


def _fake_config(gemini="real-key", groq="real-key-2"):
    return patch.multiple(
        "app.services.real_stylist.Config",
        GEMINI_API_KEY=gemini,
        GROQ_API_KEY=groq,
    )


def test_gemini_success():
    with _fake_config(), patch(
        "app.services.real_stylist._call_gemini", return_value=GOOD_PAYLOAD
    ) as mg, patch("app.services.real_stylist._call_groq") as mq:
        detected, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    mg.assert_called_once()
    mq.assert_not_called()


def test_fallback_to_groq_when_gemini_fails():
    with _fake_config(), patch(
        "app.services.real_stylist._call_gemini", side_effect=ValueError("boom")
    ) as mg, patch(
        "app.services.real_stylist._call_groq", return_value=GOOD_PAYLOAD
    ) as mq:
        detected, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    assert mg.call_count == 3  # three attempts before falling back
    mq.assert_called_once()


def test_all_fail_raises_ai_unavailable():
    with _fake_config(), patch(
        "app.services.real_stylist._call_gemini", side_effect=ValueError("boom")
    ), patch("app.services.real_stylist._call_groq", side_effect=ValueError("boom")):
        with pytest.raises(ApiError) as exc:
            get_real_recommendations(**ARGS)
    assert exc.value.code == "AI_UNAVAILABLE"


def test_retry_on_broken_json_then_success():
    with _fake_config(groq="PLACEHOLDER_REPLACE_WHEN_AVAILABLE"), patch(
        "app.services.real_stylist._call_gemini",
        side_effect=["{not valid json", GOOD_PAYLOAD],
    ) as mg:
        detected, recos = get_real_recommendations(**ARGS)
    assert len(recos) == 3
    assert mg.call_count == 2


# ------------------------------------------- outfit culture/formality (TN update)


def test_prompt_includes_two_level_style_rules():
    from app.services.real_stylist import _prompt

    p = _prompt(
        skin_tone="dusky", occasion="wedding", gender="female",
        style_preference="traditional", budget="medium", season_weather="hot",
        dress_type="saree", preferred_material="kanjivaram-silk",
        language="en", notes="", count=3, exclude=[],
        outfit_culture="tamil", outfit_formality="casual",
    )
    assert "tamil" in p and "casual" in p
    assert "Kanjivaram" in p
    assert "BOTH levels must be respected" in p
    assert "image_prompt" in p


def test_image_url_uses_llm_prompt_when_given():
    import urllib.parse
    from app.services.image_service import outfit_image_url

    url = outfit_image_url(
        "Test Saree", "desc", [{"name": "Emerald", "hex": "#0F7B4D"}],
        "female", "wedding", outfit_culture="tamil", outfit_formality="traditional",
        llm_image_prompt="full body photograph of a South Indian woman wearing emerald Kanjivaram silk saree with gold zari border",
    )
    assert "Kanjivaram" in urllib.parse.unquote(url)


def test_image_fallback_tamil_traditional():
    import urllib.parse
    from app.services.image_service import outfit_image_url

    url = outfit_image_url(
        "Silk Saree", "a saree", [{"name": "Red", "hex": "#AA0000"}],
        "female", "wedding", outfit_culture="tamil", outfit_formality="traditional",
    )
    decoded = urllib.parse.unquote(url)
    assert "Tamil" in decoded and "temple jewellery" in decoded


def test_image_fallback_tamil_casual_differs_from_traditional():
    import urllib.parse
    from app.services.image_service import outfit_image_url

    url = outfit_image_url(
        "Cotton Kurti", "a kurti", [{"name": "Blue", "hex": "#0000AA"}],
        "female", "casual", outfit_culture="tamil", outfit_formality="casual",
    )
    decoded = urllib.parse.unquote(url)
    assert "kurti" in decoded.lower() or "Chettinad" in decoded
    assert "wedding hall" not in decoded  # casual must not use the wedding scene


def test_image_fallback_western_formal():
    import urllib.parse
    from app.services.image_service import outfit_image_url

    url = outfit_image_url(
        "Business Suit", "a suit", [{"name": "Navy", "hex": "#1F3554"}],
        "male", "office", outfit_culture="western", outfit_formality="formal",
    )
    decoded = urllib.parse.unquote(url)
    assert "business suit" in decoded.lower()
    assert "Kanjivaram" not in decoded  # no ethnic bleed into western


# ----------------------------------------------------------------- age feature


def test_prompt_includes_age_rules():
    from app.services.real_stylist import _prompt

    p = _prompt(
        skin_tone="dusky", occasion="wedding", gender="female",
        style_preference="traditional", budget="medium", season_weather="hot",
        dress_type="saree", preferred_material="kanjivaram-silk",
        language="en", notes="", count=3, exclude=[],
        outfit_culture="tamil", outfit_formality="traditional", age=42,
    )
    assert "42 years old" in p
    assert "Age rules" in p
    assert "Mature adults (38-45)" in p
    assert "SAME age group" in p


def test_prompt_without_age_uses_default():
    from app.services.real_stylist import _prompt

    p = _prompt(
        skin_tone="dusky", occasion="party", gender="male",
        style_preference="casual", budget="low", season_weather="hot",
        dress_type="let-ai-decide", preferred_material="let-ai-decide",
        language="en", notes="", count=3, exclude=[],
    )
    assert "assume mid-20s" in p


def test_image_fallback_reflects_age():
    import urllib.parse
    from app.services.image_service import outfit_image_url

    url = outfit_image_url(
        "Silk Saree", "a saree", [{"name": "Red", "hex": "#AA0000"}],
        "female", "wedding", outfit_culture="tamil",
        outfit_formality="traditional", age=42,
    )
    decoded = urllib.parse.unquote(url)
    assert "early forties" in decoded


def test_image_fallback_teen_age():
    import urllib.parse
    from app.services.image_service import outfit_image_url

    url = outfit_image_url(
        "Cotton Kurti", "a kurti", [{"name": "Blue", "hex": "#0000AA"}],
        "female", "casual", outfit_culture="tamil",
        outfit_formality="casual", age=15,
    )
    decoded = urllib.parse.unquote(url)
    assert "teenage" in decoded


def test_analyze_rejects_bad_age(client_for_age):
    res = client_for_age.post(
        "/api/fashion/analyze",
        data={"skin_tone_text": "wheatish", "occasion": "party",
              "gender": "female", "age": "abc"},
        headers={"Authorization": "Bearer x"},
    )
    assert res.status_code == 400
    res = client_for_age.post(
        "/api/fashion/analyze",
        data={"skin_tone_text": "wheatish", "occasion": "party",
              "gender": "female", "age": "60"},
        headers={"Authorization": "Bearer x"},
    )
    assert res.status_code == 400


import pytest as _pytest


@_pytest.fixture()
def client_for_age():
    from unittest.mock import patch as _patch

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with _patch("app.middleware.auth_middleware.get_user_from_token") as mgu:
        mgu.return_value = {"id": "u-age", "email": "a@x.com", "full_name": "A"}
        with app.test_client() as c:
            yield c
'@
Set-Content -Path "tests\test_real_ai.py" -Value $content -Encoding UTF8
Write-Host "updated  tests\test_real_ai.py"

# ----- migrations\005_age.sql -----
$content = @'
-- HueFit migration 005: user age on analyses (users are 14-45)
-- Run once in Supabase SQL Editor. Safe to run repeatedly.
-- If you already ran the earlier 5-100 version, this replaces the constraint.

alter table public.analyses
  add column if not exists age integer;

alter table public.analyses
  drop constraint if exists analyses_age_check;

alter table public.analyses
  add constraint analyses_age_check check (age between 14 and 45);

select pg_notify('pgrst', 'reload schema');
'@
Set-Content -Path "migrations\005_age.sql" -Value $content -Encoding UTF8
Write-Host "updated  migrations\005_age.sql"

Write-Host ""
Write-Host "Styles + Age 14-45 patch applied." -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS (both required):"
Write-Host "  1. pytest -q                     (expect 80 passed, 1 skipped)"
Write-Host "  2. Supabase SQL Editor -> run migrations/005_age.sql"
Write-Host ""
Write-Host "Frontend contract (all optional):"
Write-Host "  age              = whole number 14-45"
Write-Host "  outfit_culture   = tamil | western | fusion | let-ai-decide"
Write-Host "  outfit_formality = traditional | formal | casual | party | festive | let-ai-decide"
