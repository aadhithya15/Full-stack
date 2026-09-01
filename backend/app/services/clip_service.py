"""CLIP embedding service - the 'map' of HueFit v2.

Converts images and sentences into 512-number coordinates. Similar things
land close together, so catalogue search = nearest-neighbour lookup.

Design notes:
  - Lazy singleton: the model (~350 MB, auto-downloaded once from Hugging
    Face on first use) loads only when first needed, then stays in memory.
  - Model choice is config-driven: CLIP_MODEL / CLIP_PRETRAINED env vars.
    Default: ViT-B-32 (fast on plain CPU). Phase V2-6 swaps to FashionCLIP
    by changing config only - no code changes.
  - Used OFFLINE for catalogue photos (scripts/index_catalogue.py) and LIVE
    for query sentences only (never images at request time).
"""
from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("CLIP_MODEL", "ViT-B-32")
_PRETRAINED = os.getenv("CLIP_PRETRAINED", "laion2b_s34b_b79k")

_lock = threading.Lock()
_state: dict = {}


def _load():
    """Load model once (thread-safe)."""
    if "model" in _state:
        return _state
    with _lock:
        if "model" in _state:
            return _state
        import open_clip
        import torch

        log.info("loading CLIP %s/%s (first call downloads ~350MB once)...",
                 _MODEL_NAME, _PRETRAINED)
        model, _, preprocess = open_clip.create_model_and_transforms(
            _MODEL_NAME, pretrained=_PRETRAINED
        )
        model.eval()
        _state.update(
            model=model,
            preprocess=preprocess,
            tokenizer=open_clip.get_tokenizer(_MODEL_NAME),
            torch=torch,
        )
        log.info("CLIP ready")
        return _state


def embed_text(text: str) -> list[float]:
    """Sentence -> 512 normalized coordinates."""
    st = _load()
    torch = st["torch"]
    with torch.no_grad():
        tokens = st["tokenizer"]([text])
        feats = st["model"].encode_text(tokens)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats[0].tolist()


def embed_image(image) -> list[float]:
    """PIL Image -> 512 normalized coordinates."""
    st = _load()
    torch = st["torch"]
    if image.mode != "RGB":
        image = image.convert("RGB")
    with torch.no_grad():
        tensor = st["preprocess"](image).unsqueeze(0)
        feats = st["model"].encode_image(tensor)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats[0].tolist()


def embed_images(images: list) -> list[list[float]]:
    """Batch version for the offline indexer (faster than one-by-one)."""
    st = _load()
    torch = st["torch"]
    tensors = torch.stack([
        st["preprocess"](img.convert("RGB") if img.mode != "RGB" else img)
        for img in images
    ])
    with torch.no_grad():
        feats = st["model"].encode_image(tensors)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return [f.tolist() for f in feats]


def model_info() -> dict:
    return {"model": _MODEL_NAME, "pretrained": _PRETRAINED, "loaded": "model" in _state}
