"""Skin-tone detection from an uploaded photo.

Two-layer strategy:
  1. Gemini Vision (primary) - the same free GEMINI_API_KEY; flash models
     are multimodal, so we send the image inline and ask for JSON.
  2. Pillow colour analysis (fallback) - no API at all: samples the centre
     region of the photo, averages skin-plausible pixels, and maps the
     result to a tone + undertone bucket. Cruder, but always available.

Public function:
    detect_skin_tone(image_bytes, mime) -> label string
      e.g. "warm wheatish with golden undertones" (vision)
           "medium-warm (wheatish)"               (pillow fallback)
Never raises: on total failure returns "medium neutral".
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

_VISION_PROMPT = (
    "Look at the person in this photo and describe their skin tone for "
    "fashion colour analysis. Respond with ONLY a JSON object, no markdown: "
    '{"skin_tone": "<one of: fair, light, medium, wheatish, olive, dusky, deep>", '
    '"undertone": "<one of: warm, cool, neutral>", '
    '"description": "<max 8 words describing the skin tone>"} '
    "If no person/face is clearly visible, use your best estimate from any "
    "visible skin."
)


# ------------------------------------------------------------ Gemini Vision


def _detect_with_gemini(image_bytes: bytes, mime: str) -> str | None:
    """Ask Gemini Vision. Returns a label string or None on any failure."""
    if Config.is_placeholder(Config.GEMINI_API_KEY):
        return None
    try:
        from app.services.real_stylist import GEMINI_BASE, _pick_model

        model = _pick_model("gemini")
        resp = requests.post(
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
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
        data = json.loads(text)
        tone = str(data.get("skin_tone", "")).strip().lower()
        undertone = str(data.get("undertone", "")).strip().lower()
        desc = str(data.get("description", "")).strip()
        if not tone:
            return None
        label = f"{undertone} {tone}".strip()
        if desc:
            label = f"{label} ({desc[:60]})"
        log.info("vision skin tone: %s", label)
        return label
    except Exception as exc:
        log.warning("gemini vision failed: %s: %s", type(exc).__name__, str(exc)[:120])
        return None


# --------------------------------------------------------- Pillow fallback


def _detect_with_pillow(image_bytes: bytes) -> str | None:
    """Rough skin-tone estimate from pixel colours. No AI, no network."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((256, 256))
        w, h = img.size
        # Sample the central region (faces are usually near the centre).
        crop = img.crop((w // 4, h // 6, 3 * w // 4, 5 * h // 6))
        pixels = list(crop.getdata())

        # Keep only skin-plausible pixels (simple RGB heuristic).
        skin = [
            (r, g, b)
            for (r, g, b) in pixels
            if r > 60 and g > 35 and b > 20
            and r > b and r >= g
            and (r - min(g, b)) > 10
            and abs(r - g) < 110
        ]
        if len(skin) < 50:  # not enough skin-like area; use all pixels
            skin = pixels
        n = len(skin)
        r = sum(p[0] for p in skin) / n
        g = sum(p[1] for p in skin) / n
        b = sum(p[2] for p in skin) / n

        luma = 0.299 * r + 0.587 * g + 0.114 * b
        if luma >= 200:
            depth = "fair"
        elif luma >= 170:
            depth = "light"
        elif luma >= 140:
            depth = "medium-warm (wheatish)" if r - b > 30 else "medium"
        elif luma >= 105:
            depth = "dusky"
        else:
            depth = "deep"

        # Undertone: warm skin has a higher red-to-blue ratio.
        ratio = r / max(b, 1)
        if ratio >= 1.45:
            undertone = "warm"
        elif ratio <= 1.15:
            undertone = "cool"
        else:
            undertone = "neutral"

        label = f"{undertone} {depth}"
        log.info("pillow skin tone: %s (rgb %.0f,%.0f,%.0f)", label, r, g, b)
        return label
    except Exception as exc:
        log.warning("pillow analysis failed: %s: %s", type(exc).__name__, str(exc)[:120])
        return None


# ------------------------------------------------------------------ public


def detect_skin_tone(image_bytes: bytes, mime: str) -> str:
    """Detect skin tone from a photo. Vision first, pixels second, safe default last."""
    label = _detect_with_gemini(image_bytes, mime)
    if label:
        return label
    label = _detect_with_pillow(image_bytes)
    if label:
        return label
    return "medium neutral"
