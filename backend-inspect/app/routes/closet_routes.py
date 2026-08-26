"""Digital closet endpoints: /api/closet/items."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.db import queries
from app.middleware.auth_middleware import require_auth
from app.services.storage_service import signed_url, upload_photo
from app.utils.errors import ApiError

closet_bp = Blueprint("closet", __name__)

ITEM_TYPES = {
    "shirt", "t-shirt", "blouse", "top", "saree", "dress", "skirt", "trousers",
    "pants", "jeans", "shorts", "kurta", "sherwani", "blazer", "jacket", "suit",
    "lehenga", "shoes", "sandals", "heels", "loafers", "bag", "watch", "accessories",
    "other",
}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _text(name: str, default: str = "") -> str:
    return (request.form.get(name) or default).strip()[:100]


def _serialize(row: dict) -> dict:
    image_path = row.get("image_path")
    return {
        "id": row["id"],
        "item_name": row["item_name"],
        "item_type": row["item_type"],
        "colour": row.get("colour") or "",
        "material": row.get("material") or "",
        "image_url": signed_url(image_path) if image_path else None,
        "created_at": row.get("created_at"),
    }


@closet_bp.get("/items")
@require_auth
def list_items():
    return jsonify({"success": True, "items": [_serialize(row) for row in queries.list_closet_items(g.user["id"])]})


@closet_bp.post("/items")
@require_auth
def create_item():
    item_name = _text("item_name")
    item_type = _text("item_type", "other").lower()
    colour = _text("colour")
    material = _text("material")

    if not item_name:
        raise ApiError.invalid_input("item_name is required")
    if item_type not in ITEM_TYPES:
        raise ApiError.invalid_input(f"Invalid item_type '{item_type}'")

    image = request.files.get("image")
    image_path = None
    if image is not None and image.filename:
        if image.mimetype not in ALLOWED_MIME:
            raise ApiError.invalid_input("Image must be JPEG, PNG or WebP")
        image_path = upload_photo(g.user["id"], image.read(), image.mimetype)

    row = queries.insert_closet_item(
        g.user["id"],
        {
            "item_name": item_name,
            "item_type": item_type,
            "colour": colour or None,
            "material": material or None,
            "image_path": image_path,
        },
    )
    return jsonify({"success": True, "item": _serialize(row)}), 201


@closet_bp.delete("/items/<item_id>")
@require_auth
def delete_item(item_id: str):
    row = queries.delete_closet_item(g.user["id"], item_id)
    if row is None:
        raise ApiError.not_found("Closet item not found")
    return jsonify({"success": True, "id": item_id})
