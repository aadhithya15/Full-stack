"""Profile endpoints - GET/PUT /api/profile (Phase 9)."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.db import queries
from app.middleware.auth_middleware import require_auth
from app.utils.errors import ApiError

profile_bp = Blueprint("profile", __name__)

GENDERS = {"male", "female", "neutral"}
STYLES = {"traditional", "western", "formal", "casual", "any"}
BUDGETS = {"low", "medium", "premium"}
LANGUAGES = {"en", "ta", "hi"}


@profile_bp.get("")
@require_auth
def get_profile():
    profile = queries.get_profile(g.user["id"])
    return jsonify({"success": True, "user": g.user, "profile": profile})


@profile_bp.put("")
@require_auth
def update_profile():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        raise ApiError.invalid_input("Send a JSON body with the fields to update")

    updates: dict = {}

    if "full_name" in body:
        name = str(body["full_name"]).strip()
        if not name or len(name) > 80:
            raise ApiError.invalid_input("full_name must be 1-80 characters")
        updates["full_name"] = name

    if "gender" in body:
        if body["gender"] not in GENDERS:
            raise ApiError.invalid_input(f"gender must be one of: {', '.join(sorted(GENDERS))}")
        updates["gender"] = body["gender"]

    if "skin_tone" in body:
        tone = str(body["skin_tone"]).strip()[:60]
        updates["skin_tone"] = tone or None

    if "style_preference" in body:
        if body["style_preference"] not in STYLES:
            raise ApiError.invalid_input(f"style_preference must be one of: {', '.join(sorted(STYLES))}")
        updates["style_preference"] = body["style_preference"]

    if "default_budget" in body:
        if body["default_budget"] not in BUDGETS:
            raise ApiError.invalid_input(f"default_budget must be one of: {', '.join(sorted(BUDGETS))}")
        updates["default_budget"] = body["default_budget"]

    if "language" in body:
        if body["language"] not in LANGUAGES:
            raise ApiError.invalid_input(f"language must be one of: {', '.join(sorted(LANGUAGES))}")
        updates["language"] = body["language"]

    if not updates:
        raise ApiError.invalid_input(
            "No valid fields. Updatable: full_name, gender, skin_tone, "
            "style_preference, default_budget, language"
        )

    profile = queries.upsert_profile(g.user["id"], updates)
    return jsonify({"success": True, "profile": profile})
