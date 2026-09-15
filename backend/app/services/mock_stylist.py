"""Curated fallback stylist with the same response shape as real AI.

This is not a random colour picker. Each complexion depth uses complete,
pre-validated colour stories from outfit_quality. The fallback also respects
all recommendation inputs so provider or web-search failure reduces novelty,
not availability or basic styling quality.
"""
from __future__ import annotations

import logging
import random

from app.services.outfit_quality import (
    assert_batch_quality,
    avoid_shades,
    canonical_depth,
    palette_stories,
    recommendation_issues,
    undertone,
)

_FEMALE_TAMIL = [
    ("saree", "Kanjivaram Saree"),
    ("anarkali", "South Indian Anarkali"),
    ("salwar-suit", "Tamil Salwar Suit"),
    ("kurta-palazzo", "Chettinad Kurta Palazzo"),
    ("lehenga-choli", "Half-Saree Inspired Lehenga"),
    ("sharara", "Temple-Border Sharara"),
    ("gharara", "Sungudi Gharara"),
]
_FEMALE_WESTERN = [
    ("midi-dress", "Tailored Midi Dress"),
    ("maxi-dress", "Flowing Maxi Dress"),
    ("gown", "Structured Evening Gown"),
    ("jumpsuit", "Tailored Jumpsuit"),
    ("blazer-trousers", "Blazer and Trousers"),
    ("western-coord", "Modern Western Co-ord"),
    ("skirt-blouse", "Pleated Skirt and Blouse"),
    ("jeans-top", "Smart Jeans and Top"),
    ("kaftan", "Relaxed Kaftan"),
]
_MALE_TAMIL = [
    ("kurta-dhoti", "Jibba and Veshti"),
    ("kurta-pajama", "South Indian Kurta Set"),
    ("nehru-jacket", "Chettinad Nehru Jacket"),
    ("sherwani", "Temple-Border Sherwani"),
    ("bandhgala", "Silk Bandhgala"),
    ("pathani-suit", "Handloom Pathani Suit"),
    ("shirt-trousers", "Coimbatore Cotton Shirt Look"),
]
_MALE_WESTERN = [
    ("shirt-trousers", "Shirt and Tailored Trousers"),
    ("blazer-chinos", "Blazer and Chinos"),
    ("two-piece-suit", "Two-Piece Suit"),
    ("three-piece-suit", "Three-Piece Suit"),
    ("tuxedo", "Modern Tuxedo"),
    ("polo-jeans", "Polo and Jeans"),
    ("casual-coord", "Relaxed Casual Co-ord"),
    ("formal-shirt-pants", "Formal Shirt and Trousers"),
]
_NEUTRAL = [
    ("tailored-separates", "Tailored Separates"),
    ("coord-set", "Relaxed Co-ord Set"),
    ("jumpsuit", "Structured Jumpsuit"),
    ("layered-outfit", "Light Layered Outfit"),
    ("relaxed-casual", "Relaxed Casual Set"),
    ("minimal-formal", "Minimal Formal Look"),
]

_LABELS = {
    code: label
    for code, label in (
        _FEMALE_TAMIL + _FEMALE_WESTERN + _MALE_TAMIL + _MALE_WESTERN + _NEUTRAL
    )
}

_FUSION_FEMALE = [
    ("saree", "Belted Kanjivaram Saree"),
    ("western-coord", "Chettinad Western Co-ord"),
    ("skirt-blouse", "Sungudi Skirt and Blouse"),
    ("blazer-trousers", "Temple-Border Blazer Set"),
    ("jumpsuit", "Kanjivaram-Trim Jumpsuit"),
]
_FUSION_MALE = [
    ("blazer-chinos", "Chettinad Blazer and Chinos"),
    ("nehru-jacket", "Modern Nehru Jacket Look"),
    ("shirt-trousers", "Temple-Border Shirt Look"),
    ("kurta-pajama", "Contemporary Jibba Set"),
    ("casual-coord", "Sungudi-Detail Co-ord"),
]

_ACCESSORIES = {
    "female": {
        "tamil": ["{metal} temple jhumkas", "small woven potli", "slim matching bangles"],
        "western": ["{metal} stud earrings", "structured clutch", "minimal bracelet"],
        "fusion": ["{metal} contemporary jhumkas", "clean-lined clutch", "single statement bangle"],
    },
    "male": {
        "tamil": ["{metal} dress watch", "folded angavastram", "minimal brooch"],
        "western": ["{metal} dress watch", "tonal pocket square", "matching leather belt"],
        "fusion": ["{metal} dress watch", "Chettinad pocket square", "minimal collar pin"],
    },
    "neutral": {
        "tamil": ["{metal} clean-lined watch", "woven stole", "minimal ring"],
        "western": ["{metal} clean-lined watch", "structured crossbody", "minimal ring"],
        "fusion": ["{metal} clean-lined watch", "Sungudi accent scarf", "minimal ring"],
    },
}

_FOOTWEAR = {
    "female": {
        "tamil": ["cushioned metallic sandals", "embroidered flat juttis"],
        "western": ["tonal block-heel shoes", "clean leather flats"],
        "fusion": ["metallic block-heel sandals", "minimal embroidered flats"],
    },
    "male": {
        "tamil": ["polished leather sandals", "tonal mojari shoes"],
        "western": ["polished Oxford shoes", "tonal suede-free loafers"],
        "fusion": ["polished loafers", "minimal mojari shoes"],
    },
    "neutral": {
        "tamil": ["polished leather flats", "minimal slip-on shoes"],
        "western": ["clean leather loafers", "tonal low-profile shoes"],
        "fusion": ["minimal embroidered loafers", "clean leather flats"],
    },
}

_WEATHER_FABRIC = {
    "hot": "lightweight handloom cotton",
    "humid": "breathable cotton-linen",
    "rainy": "quick-drying lightweight cotton blend",
    "winter": "layered cotton-silk",
    "any": "breathable premium cotton-silk",
}
_BUDGET_WORD = {
    "low": "attainable",
    "medium": "well-finished mid-range",
    "premium": "premium artisan-finished",
}
_VARIANTS = (
    "Classic Edit", "Modern Edit", "Clean-Line Edit", "Textured Edit",
    "Daylight Edit", "Evening Edit", "Signature Edit", "Refined Edit",
)
log = logging.getLogger(__name__)

_TRADITIONAL_OCCASIONS = {
    "wedding", "reception", "engagement", "religious-ceremony", "festival",
    "pongal", "diwali", "eid", "onam", "navratri",
}


def _resolved_culture(
    outfit_culture: str,
    style_preference: str,
    occasion: str,
) -> str:
    if outfit_culture in {"tamil", "western", "fusion"}:
        return outfit_culture
    if style_preference == "western":
        return "western"
    if style_preference == "traditional" or occasion in _TRADITIONAL_OCCASIONS:
        return "tamil"
    # Tamil-first for the target audience, while still retaining western looks.
    return random.choice(("tamil", "tamil", "western", "fusion"))


def _pool(gender: str, culture: str) -> list[tuple[str, str]]:
    if gender == "neutral":
        return list(_NEUTRAL)
    if culture == "fusion":
        return list(_FUSION_FEMALE if gender == "female" else _FUSION_MALE)
    if gender == "female":
        return list(_FEMALE_TAMIL if culture == "tamil" else _FEMALE_WESTERN)
    return list(_MALE_TAMIL if culture == "tamil" else _MALE_WESTERN)


def _formality_phrase(outfit_formality: str, style_preference: str) -> str:
    value = outfit_formality
    if value == "let-ai-decide" and style_preference in {"formal", "casual"}:
        value = style_preference
    return {
        "traditional": "ceremonial and classically draped",
        "formal": "polished and office-appropriate",
        "casual": "relaxed and easy to move in",
        "party": "evening-ready without fluorescent colour",
        "festive": "celebratory with controlled detailing",
        "let-ai-decide": "balanced for the occasion",
    }.get(value, "balanced for the occasion")


def _age_phrase(age: int | None) -> str:
    if age is None:
        return "a contemporary adult"
    if age < 18:
        return "a youthful, modest teen"
    if age <= 27:
        return "a trend-aware young adult"
    if age <= 37:
        return "a polished adult"
    return "a confident, elegantly styled adult"


def _fabric(
    preferred_material: str,
    weather: str,
    culture: str,
    occasion: str,
    outfit_type: str,
) -> str:
    selected = str(preferred_material or "").strip().lower()
    if selected not in {"", "any", "let-ai-decide"}:
        return selected.replace("-", " ")
    if culture == "tamil" and occasion in _TRADITIONAL_OCCASIONS:
        if outfit_type in {"saree", "lehenga-choli", "sherwani", "bandhgala"}:
            return "lightweight Kanjivaram silk"
        return "breathable handloom cotton-silk"
    return _WEATHER_FABRIC.get(weather, _WEATHER_FABRIC["any"])


def _garments(
    outfit_type: str,
    label: str,
    gender: str,
    main: str,
    secondary: str,
    fabric: str,
) -> list[dict]:
    code = outfit_type
    if gender == "female":
        if code == "saree":
            return [
                {"item": "saree", "name": f"{main} {label}", "colour": main, "fabric": fabric},
                {"item": "blouse", "name": f"{secondary} fitted blouse", "colour": secondary, "fabric": fabric},
            ]
        if code == "lehenga-choli":
            return [
                {"item": "lehenga", "name": f"{main} panelled lehenga", "colour": main, "fabric": fabric},
                {"item": "choli", "name": f"{secondary} structured choli", "colour": secondary, "fabric": fabric},
                {"item": "dupatta", "name": f"{secondary} light dupatta", "colour": secondary, "fabric": fabric},
            ]
        if code in {"anarkali", "salwar-suit", "kurta-palazzo", "sharara", "gharara"}:
            return [
                {"item": "kurta", "name": f"{main} {label}", "colour": main, "fabric": fabric},
                {"item": "bottom", "name": f"{secondary} coordinated bottoms", "colour": secondary, "fabric": fabric},
            ]
        if code == "blazer-trousers":
            return [
                {"item": "blazer", "name": f"{main} tailored blazer", "colour": main, "fabric": fabric},
                {"item": "trousers", "name": f"{secondary} tailored trousers", "colour": secondary, "fabric": fabric},
            ]
        if code == "jeans-top":
            return [
                {"item": "top", "name": f"{main} structured top", "colour": main, "fabric": fabric},
                {"item": "jeans", "name": f"{secondary} clean-cut jeans", "colour": secondary, "fabric": "lightweight denim"},
            ]
        if code == "skirt-blouse":
            return [
                {"item": "skirt", "name": f"{main} pleated skirt", "colour": main, "fabric": fabric},
                {"item": "blouse", "name": f"{secondary} clean-lined blouse", "colour": secondary, "fabric": fabric},
            ]
        return [
            {"item": "main garment", "name": f"{main} {label}", "colour": main, "fabric": fabric},
            {"item": "border", "name": f"{secondary} border and waist detail", "colour": secondary, "fabric": fabric},
        ]

    if gender == "male":
        if code in {"two-piece-suit", "three-piece-suit", "tuxedo", "bandhgala", "blazer-chinos", "nehru-jacket"}:
            return [
                {"item": "jacket", "name": f"{main} {label}", "colour": main, "fabric": fabric},
                {"item": "shirt", "name": f"{secondary} tailored shirt", "colour": secondary, "fabric": fabric},
                {"item": "trousers", "name": f"{main} straight trousers", "colour": main, "fabric": fabric},
            ]
        if code in {"kurta-dhoti", "kurta-pajama", "sherwani", "pathani-suit"}:
            return [
                {"item": "kurta", "name": f"{main} {label}", "colour": main, "fabric": fabric},
                {"item": "bottom", "name": f"{secondary} relaxed bottoms", "colour": secondary, "fabric": fabric},
            ]
        return [
            {"item": "shirt", "name": f"{main} {label}", "colour": main, "fabric": fabric},
            {"item": "trousers", "name": f"{secondary} tailored trousers", "colour": secondary, "fabric": fabric},
        ]

    return [
        {"item": "main piece", "name": f"{main} {label}", "colour": main, "fabric": fabric},
        {"item": "second piece", "name": f"{secondary} coordinated layer", "colour": secondary, "fabric": fabric},
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
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    age: int | None = None,
    notes: str = "",
) -> tuple[str, list[dict]]:
    """Return curated recommendations and never rely on arbitrary colour mixing."""
    exclude = exclude or []
    gender_key = gender if gender in {"female", "male", "neutral"} else "neutral"
    selected_type = str(dress_type or "").strip().lower()
    culture = _resolved_culture(outfit_culture, style_preference, occasion)
    pool = _pool(gender_key, culture)
    if selected_type not in {"", "any", "let-ai-decide"}:
        label = _LABELS.get(selected_type, selected_type.replace("-", " ").title())
        if culture == "tamil" and not any(word in label.lower() for word in ("tamil", "kanjivaram", "chettinad", "sungudi", "temple", "veshti", "jibba")):
            label = "Tamil-Detail " + label
        elif culture == "fusion" and not any(word in label.lower() for word in ("kanjivaram", "chettinad", "sungudi", "temple", "jibba", "nehru")):
            label = "Tamil-Fusion " + label
        pool = [(selected_type, label)]

    random.shuffle(pool)
    stories = palette_stories(skin_tone)
    random.shuffle(stories)
    excluded_names = {str(value).strip().lower() for value in exclude}
    budget_word = _BUDGET_WORD.get(budget, _BUDGET_WORD["medium"])
    formality = _formality_phrase(outfit_formality, style_preference)
    age_text = _age_phrase(age)

    recos: list[dict] = []
    attempts = 0
    while len(recos) < count and attempts < 500:
        outfit_type, label = pool[attempts % len(pool)]
        story = stories[attempts % len(stories)]
        main, main_hex = story["main"]
        secondary, secondary_hex = story["secondary"]
        variant_round = attempts // max(1, len(pool) * len(stories))
        suffix = "" if variant_round == 0 else f" {_VARIANTS[(variant_round - 1) % len(_VARIANTS)]} {variant_round}"
        name = f"{main} {label}{suffix}"[:80]
        attempts += 1
        if name.lower() in excluded_names or any(item["outfit_name"].lower() == name.lower() for item in recos):
            continue
        if selected_type in {"", "any", "let-ai-decide"} and any(
            item["outfit_type"] == outfit_type for item in recos
        ):
            continue
        if any(
            item["dress_colors"][0]["hex"] == main_hex
            and item["dress_colors"][1]["hex"] == secondary_hex
            for item in recos
        ):
            continue

        fabric = _fabric(preferred_material, season_weather, culture, occasion, outfit_type)
        metal = story["metal"]
        accessories = [
            item.format(metal=metal)
            for item in _ACCESSORIES[gender_key][culture]
        ]
        footwear = random.choice(_FOOTWEAR[gender_key][culture])
        garments = _garments(outfit_type, label, gender_key, main, secondary, fabric)
        tamil_detail = (
            "The regional weave or border keeps the recommendation grounded in Tamil Nadu. "
            if culture in {"tamil", "fusion"}
            else ""
        )
        description = (
            f"A {budget_word} {label.lower()} led by {main.lower()}, balanced with "
            f"{secondary.lower()} for clear, intentional contrast on a {canonical_depth(skin_tone)} "
            f"complexion. {tamil_detail}The silhouette is {formality} for {occasion} and suits {age_text}."
        )
        recommendation = {
            "outfit_name": name,
            "category": "fusion" if culture == "fusion" else "traditional" if culture == "tamil" else "western",
            "outfit_type": outfit_type,
            "materials": [fabric],
            "description": description,
            "garments": garments,
            "dress_colors": [
                {"name": main, "hex": main_hex},
                {"name": secondary, "hex": secondary_hex},
            ],
            "accessories": accessories,
            "footwear": footwear,
            "styling_tips": (
                f"Keep all metal details in {metal}; let {main.lower()} sit nearest the face "
                "and use the second colour as a controlled garment, border, or layer."
            ),
            "avoid_colors": avoid_shades(skin_tone),
            "match_score": random.randint(88, 95),
            "is_mock": True,
        }
        problems = recommendation_issues(
            recommendation,
            skin_tone=skin_tone,
            dress_type=dress_type,
            preferred_material=preferred_material,
            outfit_culture=outfit_culture,
            outfit_formality=outfit_formality,
            season_weather=season_weather,
            age=age,
            notes=notes,
        )
        if problems:
            continue
        recos.append(recommendation)

    if len(recos) < count:
        # This should only be reachable for mutually conflicting explicit
        # inputs. Use the safest stories and preserve availability.
        remaining = count - len(recos)
        for offset in range(remaining):
            story = palette_stories(skin_tone)[offset]
            main, main_hex = story["main"]
            secondary, secondary_hex = story["secondary"]
            outfit_type, label = pool[offset % len(pool)]
            fabric = _fabric(preferred_material, season_weather, culture, occasion, outfit_type)
            recos.append({
                "outfit_name": f"{main} {label} Safe Edit {offset + 1}"[:80],
                "category": "fusion" if culture == "fusion" else "traditional" if culture == "tamil" else "western",
                "outfit_type": outfit_type,
                "materials": [fabric],
                "description": f"A clear {main.lower()} and {secondary.lower()} outfit with a coherent, wearable colour story for {occasion}.",
                "garments": _garments(outfit_type, label, gender_key, main, secondary, fabric),
                "dress_colors": [{"name": main, "hex": main_hex}, {"name": secondary, "hex": secondary_hex}],
                "accessories": [item.format(metal=story["metal"]) for item in _ACCESSORIES[gender_key][culture]],
                "footwear": _FOOTWEAR[gender_key][culture][0],
                "styling_tips": f"Keep every metal detail in {story['metal']} for a clean finish.",
                "avoid_colors": avoid_shades(skin_tone),
                "match_score": 88,
                "is_mock": True,
            })

    # Protect future edits, but never turn a fallback-quality problem into an
    # unavailable analysis. Individual looks added in the main loop were
    # already validated; this final check mainly catches cross-look drift.
    try:
        assert_batch_quality(
            recos,
            count=count,
            exclude=exclude,
            skin_tone=skin_tone,
            dress_type=dress_type,
            preferred_material=preferred_material,
            outfit_culture=outfit_culture,
            outfit_formality=outfit_formality,
            season_weather=season_weather,
            age=age,
            notes=notes,
        )
    except ValueError as exc:
        log.error("curated fallback returned with relaxed conflicting constraints: %s", str(exc)[:300])

    detected = f"{canonical_depth(skin_tone)} complexion"
    stated = undertone(skin_tone)
    if stated != "unknown":
        detected += f" with {stated} undertone"

    if language != "en":
        from app.services.real_stylist import _localize_recommendation, _translate_text

        detected = _translate_text(detected, language)
        recos = [_localize_recommendation(recommendation, language) for recommendation in recos]
    return detected, recos
