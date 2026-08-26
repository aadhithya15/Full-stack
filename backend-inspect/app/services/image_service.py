"""Outfit image URLs via Pollinations.ai â€” free, keyless.

The URL itself IS the image: Pollinations generates it on first load.
We never wait for generation server-side; the user's browser fetches it.
If a stronger provider is added later, only this file changes.
"""
from __future__ import annotations

import random
import urllib.parse

BASE = "https://image.pollinations.ai/prompt/"


def outfit_image_url(
    outfit_name: str,
    description: str,
    colors: list[dict],
    gender: str,
    occasion: str,
) -> str:
    color_names = ", ".join(c.get("name", "") for c in colors[:3] if c.get("name"))
    model = {
        "male": "male model",
        "female": "female model",
    }.get(gender, "fashion model")

    prompt = (
        f"high-end fashion editorial photograph, full-body {model} wearing {outfit_name}, "
        f"{description[:160]}, colours {color_names}, {occasion} setting, "
        "sharp focus, realistic fabric texture, natural hands and face, elegant confident pose, "
        "premium studio lighting, clean uncluttered background, luxury magazine composition, "
        "photorealistic, portrait orientation, no text, no logos, no watermark"
    )
    # A random seed makes each generated look unique even for similar prompts.
    seed = random.randint(1, 10_000_000)
    return (
        BASE
        + urllib.parse.quote(prompt)
        + f"?width=1024&height=1365&nologo=true&enhance=true&seed={seed}"
    )
