"""Skin-tone detection and canonical template-tone selection.

Detection uses Gemini Vision first and a local Pillow fallback second.
Template selection uses canonical_tone() to map free text to one of the
8 skin-tone folders supplied by the design team.

Public functions:
    detect_skin_tone(image_bytes, mime) -> descriptive label
    canonical_tone(text) -> fair/light/wheatish/medium/dusky/deep/warm/cool

Every failure is safe. Detection falls back to "medium neutral" and an
unknown canonical tone returns None so callers can use the base template.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re

import requests

from app.config import Config

log = logging.getLogger(__name__)

TIMEOUT = 30
CANONICAL_TONES = (
    "fair",
    "light",
    "wheatish",
    "medium",
    "dusky",
    "deep",
    "warm",
    "cool",
)

# Depth/surface tone words are checked before undertone words. This is
# intentional: "warm wheatish with golden undertones" must use wheatish,
# not the generic warm variant.
_DEPTH_ALIASES = (
    ("wheatish", ("wheatish", "wheat", "golden beige", "honey beige")),
    ("fair", ("fair", "very fair", "porcelain", "ivory", "pale")),
    ("light", ("light", "light beige")),
    ("medium", ("medium", "olive", "tan")),
    # Check explicit deep/dark before the broad word "brown" in dusky.
    ("deep", ("deep", "dark", "ebony")),
    ("dusky", ("dusky", "caramel", "brown")),
)
_UNDERTONE_ALIASES = (
    ("warm", ("warm", "golden", "yellow undertone", "peach undertone")),
    ("cool", ("cool", "pink undertone", "blue undertone", "rosy")),
)


def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


def canonical_tone(value: str | None) -> str | None:
    """Map user/detector text to one supported template tone.

    Specific depth words win over warm/cool undertones. Unknown or empty
    input returns None, which deliberately selects the base template.
    """
    if value is None:
        return None
    text = re.sub(r"[_-]+", " ", str(value).strip().lower())
    text = re.sub(r"\s+", " ", text)
    if not text:
        return None

    # A detector label such as "medium-warm (wheatish)" explicitly marks
    # wheatish in parentheses, so wheatish is checked before medium.
    for tone, phrases in _DEPTH_ALIASES:
        if any(_has_phrase(text, phrase) for phrase in phrases):
            return tone
    for tone, phrases in _UNDERTONE_ALIASES:
        if any(_has_phrase(text, phrase) for phrase in phrases):
            return tone
    return None


_VISION_PROMPT = (
    "Look at the person in this photo and describe their skin tone for "
    "fashion colour analysis. Respond with ONLY a JSON object, no markdown: "
    '{"skin_tone": "<one of: fair, light, medium, wheatish, olive, dusky, deep>", '
    '"undertone": "<one of: warm, cool, neutral>", '
    '"description": "<max 8 words describing the skin tone>"} '
    "If no person or face is clearly visible, use your best estimate from "
    "any visible skin."
)


def _detect_with_gemini(image_bytes: bytes, mime: str) -> str | None:
    """Ask Gemini Vision. Return a label or None on any failure."""
    if Config.is_placeholder(Config.GEMINI_API_KEY):
        return None
    try:
        from app.services.real_stylist import GEMINI_BASE, _pick_model

        model = _pick_model("gemini")
        response = requests.post(
            f"{GEMINI_BASE}/models/{model}:generateContent",
            params={"key": Config.GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": mime,
                                    "data": base64.b64encode(image_bytes).decode(),
                                }
                            },
                            {"text": _VISION_PROMPT},
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
        data = json.loads(text)
        tone = str(data.get("skin_tone", "")).strip().lower()
        undertone = str(data.get("undertone", "")).strip().lower()
        description = str(data.get("description", "")).strip()
        if not tone:
            return None
        label = f"{undertone} {tone}".strip()
        if description:
            label = f"{label} ({description[:60]})"
        log.info("vision skin tone: %s", label)
        return label
    except Exception as exc:
        log.warning("gemini vision failed: %s: %s", type(exc).__name__, str(exc)[:120])
        return None


def _detect_with_pillow(image_bytes: bytes) -> str | None:
    """Estimate skin tone from pixels without AI or network access."""
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((256, 256))
        width, height = image.size
        crop = image.crop((width // 4, height // 6, 3 * width // 4, 5 * height // 6))
        pixels = list(crop.getdata())

        skin = [
            (red, green, blue)
            for (red, green, blue) in pixels
            if red > 60
            and green > 35
            and blue > 20
            and red > blue
            and red >= green
            and (red - min(green, blue)) > 10
            and abs(red - green) < 110
        ]
        if len(skin) < 50:
            skin = pixels
        count = len(skin)
        red = sum(pixel[0] for pixel in skin) / count
        green = sum(pixel[1] for pixel in skin) / count
        blue = sum(pixel[2] for pixel in skin) / count

        luma = 0.299 * red + 0.587 * green + 0.114 * blue
        if luma >= 200:
            depth = "fair"
        elif luma >= 170:
            depth = "light"
        elif luma >= 140:
            depth = "medium-warm (wheatish)" if red - blue > 30 else "medium"
        elif luma >= 105:
            depth = "dusky"
        else:
            depth = "deep"

        ratio = red / max(blue, 1)
        if ratio >= 1.45:
            undertone = "warm"
        elif ratio <= 1.15:
            undertone = "cool"
        else:
            undertone = "neutral"

        label = f"{undertone} {depth}"
        log.info(
            "pillow skin tone: %s (rgb %.0f,%.0f,%.0f)",
            label,
            red,
            green,
            blue,
        )
        return label
    except Exception as exc:
        log.warning("pillow analysis failed: %s: %s", type(exc).__name__, str(exc)[:120])
        return None


def detect_skin_tone(image_bytes: bytes, mime: str) -> str:
    """Detect skin tone with safe fallbacks and never raise."""
    label = _detect_with_gemini(image_bytes, mime)
    if label:
        return label
    label = _detect_with_pillow(image_bytes)
    if label:
        return label
    return "medium neutral"
