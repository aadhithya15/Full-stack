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

    # ---------- 4) recommendation images: TEMPLATE RECOLOURING (MVP) ----------
    # Strategy doc flow: select approved template -> stored mask ->
    # apply the LLM-recommended colour inside the mask. No generation.
    from app.services.template_service import pick_template, render_recommendation

    g_for_template = gender if gender in ("male", "female") else "unisex"
    culture_for_template = outfit_culture if outfit_culture != "let-ai-decide" else None

    def _render_one(r: dict) -> None:
        """Render one outfit's image; failures leave image_url None."""
        r.pop("image_prompt", "")  # legacy field from the generation era
        r["image_url"] = None
        r["image_source"] = "none"
        primary_hex = (r.get("dress_colors") or [{}])[0].get("hex")
        r_dress_type = (r.get("outfit_type") or dress_type or "").strip().lower()
        if not primary_hex:
            return
        try:
            tpl = pick_template(
                dress_type=r_dress_type,
                gender=g_for_template,
                culture=culture_for_template,
            )
            if tpl is not None:
                url = render_recommendation(tpl, primary_hex)
                if url:
                    r["image_url"] = url
                    r["image_source"] = "template"
                    r["template_code"] = tpl["template_code"]
        except Exception:
            pass  # image is a visual aid - never fail the recommendation for it

    # Parallel: 4 outfits render concurrently. On cache misses this turns
    # ~4x(recolour+upload) serial time into roughly one round trip.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_render_one, recos))

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
                    "image_source": row.get("image_source", "none"),
                    "template_code": row.get("template_code"),
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
