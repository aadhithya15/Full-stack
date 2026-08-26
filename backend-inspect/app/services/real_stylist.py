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
- Response language: {language_name}
{notes_block}{exclude_block}

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
        {"item": "<saree|blouse|dress|shirt|trousers|skirt|blazer|kurta|jacket|dupatta>", "name": "<specific garment name>", "colour": "<colour>", "fabric": "<fabric>"}
      ],
      "dress_colors": [{{"name": "<colour name>", "hex": "<#RRGGBB>"}}, {{"name": "...", "hex": "..."}}],
      "accessories": ["<item 1>", "<item 2>", "<item 3>"],
      "footwear": "<specific footwear suggestion>",
      "styling_tips": "<one practical styling tip>",
      "avoid_colors": [{{"name": "<colour name>", "hex": "<#RRGGBB>"}}],
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
) -> tuple[str, list[dict]]:
    prompt = _prompt(
        skin_tone, occasion, gender, style_preference,
        budget, season_weather, dress_type, preferred_material,
        language, notes, count, exclude,
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
