"""Deterministic quality floor for HueFit outfit recommendations.

The AI may suggest creative garments, but this module owns the non-negotiable
parts of a usable recommendation:

* one of the six public complexion depths is handled explicitly;
* the whole palette is checked for contrast, clarity, and internal harmony;
* weak combinations such as rust plus olive are rejected;
* selected dress type, material, culture, age, weather, and exclusions win;
* safe, curated colour stories are available when an AI provider fails.

Skin depth is not the same as undertone. The rules deliberately avoid assuming
that every deep complexion is warm or every fair complexion is cool. When the
undertone is unknown, balanced jewel tones and clean contrast are preferred.
"""
from __future__ import annotations

import colorsys
import math
import re
from typing import Iterable

PUBLIC_TONES = ("fair", "light", "wheatish", "medium", "dusky", "deep")

# Every story is a complete two-colour outfit direction, not a bag of colours
# that may be paired randomly. Hex values are fabric-realistic rather than
# fluorescent screen primaries. "metal" is used to keep jewellery coherent.
PALETTE_STORIES: dict[str, tuple[dict, ...]] = {
    "fair": (
        {"main": ("Deep Navy", "#263A5B"), "secondary": ("Dusty Rose", "#C7838F"), "metal": "silver"},
        {"main": ("Emerald Green", "#176B55"), "secondary": ("Soft Ivory", "#F1E7D0"), "metal": "gold"},
        {"main": ("Berry Pink", "#A33E68"), "secondary": ("Slate Blue", "#657AA1"), "metal": "silver"},
        {"main": ("Rich Teal", "#176B6B"), "secondary": ("Warm Blush", "#D99AA5"), "metal": "rose gold"},
        {"main": ("Aubergine", "#5A2948"), "secondary": ("Muted Lavender", "#A48BC2"), "metal": "silver"},
        {"main": ("Burgundy", "#76283B"), "secondary": ("Pearl Grey", "#C1C7CE"), "metal": "silver"},
        {"main": ("Forest Green", "#285A43"), "secondary": ("Soft Peach", "#E3A083"), "metal": "gold"},
        {"main": ("Cobalt Blue", "#3157A4"), "secondary": ("Soft Camel", "#C59A6C"), "metal": "gold"},
    ),
    "light": (
        {"main": ("Sapphire Blue", "#28529A"), "secondary": ("Powder Blue", "#A9C3DD"), "metal": "silver"},
        {"main": ("Wine Red", "#7A3048"), "secondary": ("Blush Pink", "#D7A0A8"), "metal": "rose gold"},
        {"main": ("Peacock Teal", "#176C73"), "secondary": ("Warm Ivory", "#F0E4C9"), "metal": "gold"},
        {"main": ("Royal Plum", "#63365F"), "secondary": ("Soft Mauve", "#B58BA5"), "metal": "silver"},
        {"main": ("Warm Coral", "#C95F55"), "secondary": ("Deep Navy", "#263A5B"), "metal": "gold"},
        {"main": ("Emerald Green", "#176B55"), "secondary": ("Soft Champagne", "#DCC79F"), "metal": "gold"},
        {"main": ("Charcoal Blue", "#3F4C5E"), "secondary": ("Rose Pink", "#C7788D"), "metal": "silver"},
        {"main": ("Terracotta", "#B85F45"), "secondary": ("Cream", "#EEDFC5"), "metal": "gold"},
    ),
    "wheatish": (
        {"main": ("Peacock Teal", "#126A70"), "secondary": ("Antique Gold", "#C59A43"), "metal": "gold"},
        {"main": ("Ruby Maroon", "#7C2638"), "secondary": ("Warm Ivory", "#EFE1C5"), "metal": "gold"},
        {"main": ("Royal Plum", "#63305E"), "secondary": ("Marigold", "#D39A2C"), "metal": "gold"},
        {"main": ("Cobalt Blue", "#2855A0"), "secondary": ("Soft Peach", "#E49B78"), "metal": "gold"},
        {"main": ("Emerald Green", "#126B4E"), "secondary": ("Rani Pink", "#B52D67"), "metal": "gold"},
        {"main": ("Burgundy", "#76283B"), "secondary": ("Warm Camel", "#BE8F5A"), "metal": "gold"},
        {"main": ("Terracotta", "#B85F45"), "secondary": ("Deep Teal", "#205D61"), "metal": "gold"},
        {"main": ("Deep Navy", "#263A5B"), "secondary": ("Warm Coral", "#D16A5D"), "metal": "rose gold"},
    ),
    "medium": (
        {"main": ("Emerald Green", "#126B4E"), "secondary": ("Antique Gold", "#C59A43"), "metal": "gold"},
        {"main": ("Royal Blue", "#2C4F9E"), "secondary": ("Warm Ivory", "#EFE1C5"), "metal": "gold"},
        {"main": ("Burgundy", "#76283B"), "secondary": ("Dusty Blush", "#CB8C97"), "metal": "rose gold"},
        {"main": ("Deep Teal", "#155F65"), "secondary": ("Warm Coral", "#D0695D"), "metal": "gold"},
        {"main": ("Royal Plum", "#63305E"), "secondary": ("Soft Champagne", "#D8C092"), "metal": "gold"},
        {"main": ("Forest Green", "#285A43"), "secondary": ("Saffron Gold", "#D29A2E"), "metal": "gold"},
        {"main": ("Burnished Rust", "#A84F32"), "secondary": ("Deep Navy", "#263A5B"), "metal": "gold"},
        {"main": ("Olive Green", "#66713C"), "secondary": ("Clear Cream", "#EBDDBF"), "metal": "gold"},
    ),
    "dusky": (
        {"main": ("Rani Pink", "#B52D67"), "secondary": ("Antique Gold", "#C59A43"), "metal": "gold"},
        {"main": ("Cobalt Blue", "#2855A0"), "secondary": ("Warm Ivory", "#F0E2C7"), "metal": "gold"},
        {"main": ("Emerald Green", "#126B4E"), "secondary": ("Deep Pink", "#C13E73"), "metal": "gold"},
        {"main": ("Ruby Red", "#A72E3E"), "secondary": ("Soft Champagne", "#D8C092"), "metal": "gold"},
        {"main": ("Peacock Teal", "#126A70"), "secondary": ("Marigold", "#D49A2A"), "metal": "gold"},
        {"main": ("Amethyst Purple", "#67458A"), "secondary": ("Soft Silver", "#C3C6CC"), "metal": "silver"},
        {"main": ("Vivid Coral", "#D35E54"), "secondary": ("Midnight Navy", "#202F4F"), "metal": "gold"},
        {"main": ("Crisp White", "#F5F1E8"), "secondary": ("Temple Gold", "#BE8D31"), "metal": "gold"},
    ),
    "deep": (
        {"main": ("Cobalt Blue", "#2855A0"), "secondary": ("Warm Ivory", "#F0E2C7"), "metal": "gold"},
        {"main": ("Rani Pink", "#B52D67"), "secondary": ("Antique Gold", "#C59A43"), "metal": "gold"},
        {"main": ("Emerald Green", "#126B4E"), "secondary": ("Soft Champagne", "#D8C092"), "metal": "gold"},
        {"main": ("Ruby Red", "#A72E3E"), "secondary": ("Crisp Cream", "#EFE2C8"), "metal": "gold"},
        {"main": ("Amethyst Purple", "#67458A"), "secondary": ("Soft Silver", "#C3C6CC"), "metal": "silver"},
        {"main": ("Peacock Teal", "#126A70"), "secondary": ("Marigold", "#D49A2A"), "metal": "gold"},
        {"main": ("Vivid Coral", "#D35E54"), "secondary": ("Midnight Navy", "#202F4F"), "metal": "gold"},
        {"main": ("Crisp White", "#F5F1E8"), "secondary": ("Temple Gold", "#BE8D31"), "metal": "gold"},
    ),
}

AVOID_SHADE_STORIES: dict[str, tuple[tuple[str, str], ...]] = {
    "fair": (("Skin-Matching Pale Beige", "#E8D6C4"), ("Fluorescent Yellow", "#E9F542")),
    "light": (("Washed-Out Beige", "#D9C7AE"), ("Fluorescent Lime", "#B7F531")),
    "wheatish": (("Ashy Beige", "#AAA08F"), ("Fluorescent Green", "#45F02D")),
    "medium": (("Muddy Taupe", "#766B5F"), ("Fluorescent Pink", "#F447AA")),
    "dusky": (("Muddy Brown", "#5C493D"), ("Ash Grey", "#777B7D")),
    "deep": (("Muddy Brown", "#4E4037"), ("Ash Grey", "#6D7376")),
}

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_WORD_RE = re.compile(r"[a-z]+")
_EARTH_WORDS = {"rust", "rusty", "olive", "khaki", "camel", "taupe", "moss", "mud", "muddy", "brown", "terracotta", "ochre"}
_METAL_WORDS = {"gold", "golden", "silver", "bronze", "copper", "champagne"}
_NOTE_COLOUR_WORDS = {
    "aqua", "beige", "black", "blue", "blush", "bronze", "brown",
    "burgundy", "camel", "champagne", "charcoal", "cobalt", "copper",
    "coral", "cream", "emerald", "fuchsia", "gold", "golden", "green",
    "grey", "gray", "ivory", "khaki", "lavender", "magenta", "marigold",
    "maroon", "mauve", "mustard", "navy", "ochre", "olive", "orange",
    "peach", "pink", "plum", "purple", "red", "rose", "ruby", "rust",
    "rusty", "saffron", "sage", "silver", "taupe", "teal", "terracotta",
    "turquoise", "violet", "white", "wine", "yellow",
}
_IGNORE_COLOUR_WORDS = {
    "antique", "bright", "burnished", "clear", "crisp", "deep", "dusty",
    "light", "midnight", "muted", "peacock", "pearl", "pure", "rich",
    "royal", "soft", "temple", "vivid", "warm",
}
_HEAVY_HOT_FABRICS = {"cashmere", "fleece", "heavy wool", "tweed", "velvet"}
_SHOPPING_RE = re.compile(
    r"https?://|www\.|\bbuy\b|\bshop\b|\bcheckout\b|\bproduct link\b|"
    r"\bamazon\b|\bflipkart\b|\bmyntra\b|\bmeesho\b|(?:rs\.?|inr|usd)\s*\d",
    re.IGNORECASE,
)


def _words(value: object) -> set[str]:
    return set(_WORD_RE.findall(str(value or "").lower()))


def canonical_depth(skin_tone: str | None) -> str:
    """Return one of the six public depths, prioritising user selection."""
    text = str(skin_tone or "").lower().replace("_", " ").replace("-", " ")
    selected = re.search(r"user\s+selected\s*:\s*([a-z -]+)", text)
    if selected:
        chosen = canonical_depth(selected.group(1))
        if chosen:
            return chosen

    aliases = (
        ("deep", ("deep", "dark", "ebony")),
        ("dusky", ("dusky", "caramel", "medium dark")),
        ("wheatish", ("wheatish", "wheat", "honey beige", "golden beige")),
        ("fair", ("fair", "porcelain", "very pale")),
        ("light", ("light", "pale", "light beige")),
        ("medium", ("medium", "tan", "brown", "olive")),
    )
    for depth, terms in aliases:
        if any(re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text) for term in terms):
            return depth
    return "medium"


def undertone(skin_tone: str | None) -> str:
    text = str(skin_tone or "").lower()
    for value in ("neutral", "warm", "cool"):
        if re.search(r"(?<![a-z])" + value + r"(?![a-z])", text):
            return value
    return "unknown"


def palette_stories(skin_tone: str | None) -> list[dict]:
    return [dict(story) for story in PALETTE_STORIES[canonical_depth(skin_tone)]]


def avoid_shades(skin_tone: str | None) -> list[dict]:
    return [
        {"name": name, "hex": hex_value}
        for name, hex_value in AVOID_SHADE_STORIES[canonical_depth(skin_tone)]
    ]


def tone_colour_guide(skin_tone: str | None) -> str:
    """Build a compact, explicit guide for the generation prompt."""
    depth = canonical_depth(skin_tone)
    tone = undertone(skin_tone)
    pairs = "; ".join(
        f"{story['main'][0]} {story['main'][1]} + "
        f"{story['secondary'][0]} {story['secondary'][1]}"
        for story in PALETTE_STORIES[depth][:6]
    )
    depth_rules = {
        "fair": "Use one defined mid/deep anchor so the outfit does not wash into the complexion; soft colour is welcome as the counterpoint.",
        "light": "Prefer clear mid-depth anchors with a softer or lighter counterpoint; avoid two pale beige-grey shades together.",
        "wheatish": "Rich teal, blue, plum, ruby, green, coral, and controlled warm earth shades work well; keep earth tones crisp and contrasted.",
        "medium": "Use rich jewel or clear warm anchors with deliberate value contrast; do not build an all-muddy neutral story.",
        "dusky": "Prioritise clear saturated jewel tones, luminous lights, and intentional metallic accents; avoid dark muted earth-on-earth stories.",
        "deep": "Prioritise clear saturated jewel tones, crisp cream or white, and luminous metallic accents; avoid dark muted earth-on-earth stories.",
    }[depth]
    undertone_rule = (
        f"The stated undertone is {tone}; use {'gold/bronze and warm-biased hues' if tone == 'warm' else 'silver/pewter and cool-biased hues' if tone == 'cool' else 'balanced warm/cool colour relationships'} where appropriate."
        if tone != "unknown"
        else "Undertone is unknown. Do not invent one; use balanced jewel tones or clean neutral contrast and either one coherent metal family."
    )
    return (
        f"Six-tone depth: {depth}. {depth_rules} {undertone_rule}\n"
        f"Pre-validated colour-story directions: {pairs}.\n"
        "These are directions, not random swatches. Never pair rust with olive. "
        "Never combine two muddy earth shades. An earthy shade may be used only "
        "with a clean cream, navy, or jewel counterpoint and only when undertone "
        "or an explicit user request supports it."
    )


def _rgb(hex_value: str) -> tuple[float, float, float]:
    return tuple(int(hex_value[index:index + 2], 16) / 255.0 for index in (1, 3, 5))


def _hsv(hex_value: str) -> tuple[float, float, float]:
    hue, saturation, value = colorsys.rgb_to_hsv(*_rgb(hex_value))
    return hue * 360.0, saturation, value


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _luminance(hex_value: str) -> float:
    red, green, blue = (_linear(channel) for channel in _rgb(hex_value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _rgb_distance(first: str, second: str) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(_rgb(first), _rgb(second))))


def _hue_distance(first: float, second: float) -> float:
    difference = abs(first - second)
    return min(difference, 360.0 - difference)


def _colour_family(name: str) -> str | None:
    words = _words(name)
    families = (
        ("teal", {"teal", "turquoise", "aqua"}),
        ("blue", {"blue", "navy", "cobalt", "sapphire"}),
        ("green", {"green", "emerald", "forest", "sage", "olive"}),
        ("yellow", {"yellow", "mustard", "marigold", "saffron", "gold", "golden"}),
        ("orange", {"orange", "rust", "rusty", "terracotta", "coral", "peach"}),
        ("red", {"red", "ruby", "maroon", "burgundy", "wine", "crimson"}),
        ("pink", {"pink", "fuchsia", "magenta", "rose", "blush", "mauve"}),
        ("purple", {"purple", "plum", "amethyst", "violet", "lavender", "aubergine"}),
    )
    return next((family for family, candidates in families if words & candidates), None)


def _family_matches_hex(name: str, hex_value: str) -> bool:
    family = _colour_family(name)
    if family is None:
        return True
    hue, saturation, _ = _hsv(hex_value)
    if saturation < 0.13:
        return False
    if family == "red":
        return hue >= 330 or hue <= 25
    if family == "pink":
        return hue >= 320 or hue <= 8
    ranges = {
        "orange": (0, 55),
        "yellow": (32, 78),
        "green": (65, 178),
        "teal": (155, 205),
        "blue": (185, 265),
        "purple": (250, 330),
    }
    low, high = ranges[family]
    return low <= hue <= high


def _slug(value: object) -> str:
    return "-".join(_WORD_RE.findall(str(value or "").lower()))


def _name_matches_garment(colour_name: str, garment: dict) -> bool:
    colour_words = _words(colour_name) - _IGNORE_COLOUR_WORDS
    garment_words = _words(
        f"{garment.get('colour', '')} {garment.get('name', '')}"
    )
    if not colour_words:
        return True
    if colour_words & garment_words:
        return True
    family = _colour_family(colour_name)
    return bool(family and family in garment_words)


def _note_forbidden_words(notes: str) -> set[str]:
    forbidden: set[str] = set()
    for match in re.finditer(
        r"(?:avoid|no|without|do not use|do not wear)\s+([^.;]{1,180})",
        str(notes or "").lower(),
    ):
        phrase = re.split(
            r"\b(?:but|except|instead|prefer|choose|please use|use)\b",
            match.group(1),
            maxsplit=1,
        )[0]
        forbidden.update(_words(phrase) & _NOTE_COLOUR_WORDS)
    return forbidden


def recommendation_issues(
    recommendation: dict,
    *,
    skin_tone: str,
    dress_type: str = "let-ai-decide",
    preferred_material: str = "let-ai-decide",
    outfit_culture: str = "let-ai-decide",
    outfit_formality: str = "let-ai-decide",
    season_weather: str = "any",
    age: int | None = None,
    notes: str = "",
) -> list[str]:
    """Return deterministic quality problems for one normalized outfit."""
    issues: list[str] = []
    depth = canonical_depth(skin_tone)
    stated_undertone = undertone(skin_tone)
    colours = recommendation.get("dress_colors") or []
    garments = recommendation.get("garments") or []
    materials = recommendation.get("materials") or []

    if not 2 <= len(colours) <= 3:
        issues.append("dress_colors must contain 2 or 3 coordinated colours")
        return issues

    parsed: list[tuple[str, str, float, float, float]] = []
    for index, colour in enumerate(colours):
        if not isinstance(colour, dict):
            issues.append(f"colour {index + 1} is not an object")
            continue
        name = str(colour.get("name", "")).strip()
        hex_value = str(colour.get("hex", "")).strip().upper()
        if not name or not _HEX_RE.match(hex_value):
            issues.append(f"colour {index + 1} needs a real name and #RRGGBB hex")
            continue
        hue, saturation, value = _hsv(hex_value)
        parsed.append((name, hex_value, hue, saturation, value))
        if re.search(r"\b(neon|fluorescent)\b", name, re.IGNORECASE):
            issues.append(f"{name} is fluorescent")
        red, green, blue = _rgb(hex_value)
        if saturation > 0.96 and value > 0.96 and min(red, green, blue) < 0.04:
            issues.append(f"{name} uses a pure screen-primary hex")
        if not _family_matches_hex(name, hex_value):
            issues.append(f"{name} does not match its hex {hex_value}")

    if len(parsed) != len(colours):
        return issues

    for first_index in range(len(parsed)):
        for second_index in range(first_index + 1, len(parsed)):
            first = parsed[first_index]
            second = parsed[second_index]
            if _rgb_distance(first[1], second[1]) < 0.13:
                issues.append(f"{first[0]} and {second[0]} are visually duplicated")

    names_words = [_words(item[0]) for item in parsed]
    all_words = set().union(*names_words)
    if ({"rust", "olive"} <= all_words) or ({"rusty", "olive"} <= all_words):
        issues.append("rust and olive form a weak muddy pairing")

    earthy_count = sum(bool(words & _EARTH_WORDS) for words in names_words)
    if depth in {"dusky", "deep"} and earthy_count >= 2:
        issues.append("dusky/deep palettes cannot use two muted earth shades")

    if depth in {"dusky", "deep"}:
        main_words = names_words[0]
        if main_words & _EARTH_WORDS and stated_undertone != "warm":
            requested_words = _words(notes)
            if not (main_words & requested_words):
                issues.append("an earthy main colour needs a warm undertone or explicit request")
        clear_or_luminous = [
            (saturation >= 0.43 and 0.34 <= value <= 0.94)
            or (value >= 0.72 and saturation <= 0.48)
            or bool(words & _METAL_WORDS)
            for (_, _, _, saturation, value), words in zip(parsed, names_words)
        ]
        if not any(clear_or_luminous):
            issues.append("dusky/deep palette needs a clear saturated or luminous colour")

    if depth in {"fair", "light"}:
        if all(saturation < 0.24 and value > 0.76 for _, _, _, saturation, value in parsed):
            issues.append("fair/light palette is too pale and may wash out")

    luminances = [_luminance(item[1]) for item in parsed]
    hue_spread = max(
        (_hue_distance(a[2], b[2]) for i, a in enumerate(parsed) for b in parsed[i + 1:]),
        default=0.0,
    )
    if max(luminances) - min(luminances) < 0.055 and hue_spread < 32:
        issues.append("palette lacks both value contrast and hue contrast")
    if all(item[3] < 0.18 for item in parsed) and max(luminances) - min(luminances) < 0.20:
        issues.append("palette is an indistinct all-neutral story")

    if len(garments) < len(colours):
        issues.append("each dress colour needs a matching ordered garment or border entry")
    else:
        for index, colour in enumerate(parsed):
            garment = garments[index]
            if not isinstance(garment, dict) or not garment.get("item") or not garment.get("name"):
                issues.append(f"garment {index + 1} is incomplete")
                continue
            if not garment.get("fabric"):
                issues.append(f"garment {index + 1} has no fabric")
            if not _name_matches_garment(colour[0], garment):
                issues.append(f"dress colour {colour[0]} does not match garment {index + 1}")

    if not materials:
        issues.append("materials cannot be empty")
    if len(recommendation.get("accessories") or []) < 2:
        issues.append("at least two coherent accessories are required")
    if not str(recommendation.get("footwear", "")).strip():
        issues.append("footwear is missing")

    full_text = " ".join(
        str(value)
        for value in (
            recommendation.get("outfit_name", ""),
            recommendation.get("description", ""),
            recommendation.get("styling_tips", ""),
            recommendation.get("materials", []),
            recommendation.get("garments", []),
            recommendation.get("accessories", []),
            recommendation.get("footwear", ""),
        )
    )
    if _SHOPPING_RE.search(full_text):
        issues.append("shopping, price, brand, or URL content is not allowed")

    text_words = _words(full_text)
    if "gold" in text_words and "silver" in text_words and not ({"mixed", "metal"} <= text_words):
        issues.append("gold and silver accessories are mixed without an intentional mixed-metal plan")

    requested_type = _slug(dress_type)
    actual_type = _slug(recommendation.get("outfit_type"))
    if requested_type not in {"", "any", "let-ai-decide"} and actual_type != requested_type:
        issues.append(f"requested dress type {requested_type} was not respected")

    requested_material = _slug(preferred_material)
    if requested_material not in {"", "any", "let-ai-decide"}:
        fabric_text = _slug(" ".join(str(value) for value in materials) + " " + str(garments))
        required_parts = set(requested_material.split("-"))
        if not required_parts.issubset(set(fabric_text.split("-"))):
            issues.append(f"requested material {requested_material} was not respected")

    fabric_text_plain = " ".join(str(value).lower() for value in materials)
    if season_weather in {"hot", "humid"} and requested_material in {"", "any", "let-ai-decide"}:
        if any(heavy in fabric_text_plain for heavy in _HEAVY_HOT_FABRICS):
            issues.append("heavy insulating fabric conflicts with hot/humid weather")
    if season_weather == "rainy" and "suede" in fabric_text_plain and requested_material in {"", "any", "let-ai-decide"}:
        issues.append("suede is impractical for rainy weather")

    category = _slug(recommendation.get("category"))
    if outfit_culture == "western" and category not in {"western", "formal", "casual"}:
        issues.append("western culture choice was not respected")
    if outfit_culture == "fusion" and category != "fusion":
        issues.append("fusion culture choice was not respected")
    if outfit_culture == "tamil":
        regional_words = {
            "tamil", "kanjivaram", "sungudi", "chettinad", "coimbatore",
            "veshti", "angavastram", "jibba", "temple", "korvai", "madurai",
        }
        traditional_types = {
            "saree", "kurta-dhoti", "kurta-pajama", "anarkali", "salwar-suit",
            "kurta-palazzo", "lehenga-choli", "sharara", "gharara", "nehru-jacket",
            "sherwani", "bandhgala",
        }
        if not (text_words & regional_words) and actual_type not in traditional_types:
            issues.append("Tamil choice needs a Tamil garment, weave, or styling detail")

    if age is not None and age < 18:
        adult_terms = {"plunging", "revealing", "seductive", "bodycon", "sexy"}
        if text_words & adult_terms:
            issues.append("teen recommendation contains adult styling")

    forbidden = _note_forbidden_words(notes)
    if forbidden:
        colour_words = set().union(*names_words)
        conflict = forbidden & colour_words
        if conflict:
            issues.append("user note excluded colour(s): " + ", ".join(sorted(conflict)))

    return issues


def batch_issues(
    recommendations: list[dict],
    *,
    count: int,
    exclude: Iterable[str] = (),
    **context,
) -> list[str]:
    """Return per-look and cross-look issues for a complete recommendation set."""
    issues: list[str] = []
    if len(recommendations) != count:
        issues.append(f"expected {count} recommendations, received {len(recommendations)}")
        return issues

    excluded = {_slug(value) for value in exclude if _slug(value)}
    seen_names: set[str] = set()
    seen_palettes: set[tuple[str, ...]] = set()
    seen_types: set[str] = set()
    main_families: set[str] = set()

    for index, recommendation in enumerate(recommendations):
        name = _slug(recommendation.get("outfit_name"))
        if not name:
            issues.append(f"look {index + 1} has no outfit name")
        elif name in seen_names:
            issues.append(f"look {index + 1} repeats an outfit name")
        elif name in excluded:
            issues.append(f"look {index + 1} repeats an excluded outfit")
        seen_names.add(name)

        colours = recommendation.get("dress_colors") or []
        signature = tuple(
            str(colour.get("hex", "")).upper()
            for colour in colours
            if isinstance(colour, dict)
        )
        if signature in seen_palettes:
            issues.append(f"look {index + 1} repeats a colour palette")
        seen_palettes.add(signature)

        if colours and isinstance(colours[0], dict):
            family = _colour_family(str(colours[0].get("name", "")))
            if family:
                main_families.add(family)

        outfit_type = _slug(recommendation.get("outfit_type"))
        requested_type = _slug(context.get("dress_type", "let-ai-decide"))
        if requested_type in {"", "any", "let-ai-decide"}:
            if outfit_type in seen_types:
                issues.append(f"look {index + 1} repeats a silhouette")
            seen_types.add(outfit_type)

        for detail in recommendation_issues(recommendation, **context):
            issues.append(f"look {index + 1}: {detail}")

    if count >= 3 and len(main_families) < 2:
        issues.append("the set needs at least two distinct main colour families")
    return issues


def assert_batch_quality(recommendations: list[dict], **context) -> None:
    problems = batch_issues(recommendations, **context)
    if problems:
        raise ValueError("; ".join(problems[:10]))
