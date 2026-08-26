"""All database reads/writes in one place.

Every function takes user_id explicitly and filters on it â€” this is the
ownership enforcement layer (the service key bypasses RLS, so THIS code
is what keeps users out of each other's data).

Phase 2 ships the profile + analysis + recommendation + saved-look
functions that later phases (3, 4, 8, 9) will call.
"""
from __future__ import annotations

from typing import Any

from app.db.supabase_client import get_supabase

# ---------------------------------------------------------------- profiles


def get_profile(user_id: str) -> dict[str, Any] | None:
    res = (
        get_supabase()
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def upsert_profile(user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "full_name",
        "gender",
        "skin_tone",
        "style_preference",
        "default_budget",
        "language",
    }
    clean = {k: v for k, v in fields.items() if k in allowed}
    clean["id"] = user_id
    res = get_supabase().table("profiles").upsert(clean).execute()
    return res.data[0]


# ---------------------------------------------------------------- analyses


def insert_analysis(user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    row = {**fields, "user_id": user_id}
    # New style-catalog columns may not be visible to an existing PostgREST
    # schema cache immediately after migration. Retry without only those
    # optional columns so the AI result is never lost.
    for _ in range(3):
        try:
            res = get_supabase().table("analyses").insert(row).execute()
            return res.data[0]
        except Exception as exc:
            missing = str(exc).lower()
            optional = {field for field in ("dress_type", "preferred_material") if field in missing}
            if not optional:
                raise
            row = {k: v for k, v in row.items() if k not in optional}
    raise RuntimeError("Could not insert analysis after schema compatibility retries")


def list_analyses(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    res = (
        get_supabase()
        .table("analyses")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


# ---------------------------------------------------------- recommendations


def insert_recommendations(
    user_id: str, analysis_id: str, recos: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = [
        {**r, "user_id": user_id, "analysis_id": analysis_id} for r in recos
    ]
    # Optional style-catalog columns were added after the initial schema.
    # Retry without only the column named by Supabase so older local projects
    # can still return a real AI recommendation while migrations are applied.
    for _ in range(4):
        try:
            res = get_supabase().table("recommendations").insert(rows).execute()
            return res.data
        except Exception as exc:
            missing = str(exc).lower()
            optional = {field for field in ("garments", "outfit_type", "materials") if field in missing}
            if not optional:
                raise
            rows = [{k: v for k, v in row.items() if k not in optional} for row in rows]
    raise RuntimeError("Could not insert recommendations after schema compatibility retries")


def get_recommendation(user_id: str, recommendation_id: str) -> dict[str, Any] | None:
    res = (
        get_supabase()
        .table("recommendations")
        .select("*")
        .eq("id", recommendation_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def list_past_outfit_names(user_id: str, limit: int = 30) -> list[str]:
    """Names of recent outfits â€” used for anti-repetition exclusions."""
    res = (
        get_supabase()
        .table("recommendations")
        .select("outfit_name")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [r["outfit_name"] for r in res.data]


# ------------------------------------------------------------- saved looks


def save_look(
    user_id: str, recommendation_id: str, is_favourite: bool = False
) -> dict[str, Any]:
    res = (
        get_supabase()
        .table("saved_looks")
        .upsert(
            {
                "user_id": user_id,
                "recommendation_id": recommendation_id,
                "is_favourite": is_favourite,
            },
            on_conflict="user_id,recommendation_id",
        )
        .execute()
    )
    return res.data[0]


def list_saved_looks(user_id: str) -> list[dict[str, Any]]:
    """Saved looks with the full recommendation embedded (FK join)."""
    res = (
        get_supabase()
        .table("saved_looks")
        .select("id, is_favourite, saved_at, recommendation:recommendations(*)")
        .eq("user_id", user_id)
        .order("saved_at", desc=True)
        .execute()
    )
    return res.data


def set_favourite(user_id: str, saved_look_id: str, is_favourite: bool) -> bool:
    res = (
        get_supabase()
        .table("saved_looks")
        .update({"is_favourite": is_favourite})
        .eq("id", saved_look_id)
        .eq("user_id", user_id)  # ownership check
        .execute()
    )
    return bool(res.data)


def delete_saved_look(user_id: str, saved_look_id: str) -> bool:
    res = (
        get_supabase()
        .table("saved_looks")
        .delete()
        .eq("id", saved_look_id)
        .eq("user_id", user_id)  # ownership check
        .execute()
    )
    return bool(res.data)

# ------------------------------------------------------------- digital closet


def insert_closet_item(user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    row = {**fields, "user_id": user_id}
    res = get_supabase().table("closet_items").insert(row).execute()
    return res.data[0]


def list_closet_items(user_id: str) -> list[dict[str, Any]]:
    res = (
        get_supabase()
        .table("closet_items")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def delete_closet_item(user_id: str, item_id: str) -> dict[str, Any] | None:
    res = (
        get_supabase()
        .table("closet_items")
        .delete()
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data[0] if res.data else None
