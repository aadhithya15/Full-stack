"""All database reads/writes in one place.

Every function takes user_id explicitly and filters on it " this is the
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
            optional = {field for field in ("garments", "outfit_type", "materials", "image_source", "template_code") if field in missing}
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
    """Names of recent outfits " used for anti-repetition exclusions."""
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


# ---------------------------------------------------- v2 product catalogue


def get_or_create_client(name: str) -> dict[str, Any]:
    """Find a catalogue client by name, creating it if new."""
    sb = get_supabase()
    res = (
        sb.table("catalog_clients").select("*").eq("name", name).limit(1).execute()
    )
    if res.data:
        return res.data[0]
    res = sb.table("catalog_clients").insert({"name": name}).execute()
    return res.data[0]


def upsert_product(client_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Insert or update one product row (identified by client + title)."""
    sb = get_supabase()
    existing = (
        sb.table("products")
        .select("id")
        .eq("client_id", client_id)
        .eq("title", fields.get("title"))
        .limit(1)
        .execute()
    )
    row = {**fields, "client_id": client_id}
    if existing.data:
        res = (
            sb.table("products")
            .update(row)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        res = sb.table("products").insert(row).execute()
    return res.data[0]


def count_products(client_id: str | None = None) -> int:
    sb = get_supabase()
    q = sb.table("products").select("id", count="exact").limit(0)
    if client_id:
        q = q.eq("client_id", client_id)
    return q.execute().count or 0


def search_products_by_vector(
    embedding: list[float],
    gender: str | None = None,
    culture: str | None = None,
    occasion: str | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Nearest-neighbour search over product embeddings via the RPC helper.

    Uses the match_products SQL function (created in migration 006b) so the
    HNSW index is applied server-side. Returns rows with a `similarity`
    column (1.0 = identical direction, 0.0 = unrelated).
    """
    sb = get_supabase()
    res = sb.rpc(
        "match_products",
        {
            "query_embedding": embedding,
            "match_count": limit,
            "filter_gender": gender,
            "filter_culture": culture,
            "filter_occasion": occasion,
        },
    ).execute()
    return res.data or []


def list_products(client_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    sb = get_supabase()
    q = sb.table("products").select(
        "id, title, gender, dress_type, culture, occasions, dominant_hex, "
        "hue_family, tags, price, currency, image_url, buy_url, in_stock, indexed_at"
    ).limit(limit)
    if client_id:
        q = q.eq("client_id", client_id)
    return q.execute().data or []


# ------------------------------------------------------- outfit templates


def upsert_template(fields: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a template row (identified by template_code)."""
    sb = get_supabase()
    code = fields.get("template_code")
    existing = (
        sb.table("outfit_templates")
        .select("id")
        .eq("template_code", code)
        .limit(1)
        .execute()
    )
    if existing.data:
        res = (
            sb.table("outfit_templates")
            .update(fields)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        res = sb.table("outfit_templates").insert(fields).execute()
    return res.data[0]


def select_templates(
    dress_type: str | None = None,
    gender: str | None = None,
    culture: str | None = None,
    style_tag: str | None = None,
    only_active: bool = True,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find selectable templates for the runtime flow.

    Runtime selection only ever sees active + QA-approved templates.
    """
    sb = get_supabase()
    q = sb.table("outfit_templates").select("*").limit(limit)
    if only_active:
        q = q.eq("active_status", True).eq("qa_status", "approved")
    if dress_type:
        q = q.eq("dress_type", dress_type)
    if gender:
        q = q.eq("gender", gender)
    if culture:
        q = q.eq("culture", culture)
    if style_tag:
        q = q.contains("style_tags", [style_tag])
    return q.execute().data or []


def set_template_qa(template_code: str, qa_status: str, active: bool) -> bool:
    sb = get_supabase()
    res = (
        sb.table("outfit_templates")
        .update({"qa_status": qa_status, "active_status": active})
        .eq("template_code", template_code)
        .execute()
    )
    return bool(res.data)


def count_templates(only_active: bool = False) -> int:
    sb = get_supabase()
    q = sb.table("outfit_templates").select("id", count="exact").limit(0)
    if only_active:
        q = q.eq("active_status", True).eq("qa_status", "approved")
    return q.execute().count or 0
