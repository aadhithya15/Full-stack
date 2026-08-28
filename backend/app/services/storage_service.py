"""Supabase Storage â€” private bucket for user skin photos.

Bucket: 'user-uploads' (create it once; see scripts in migrations/ or run
check_supabase.py which creates it automatically if missing).

Photos are stored privately; we hand out short-lived signed URLs only.
"""
from __future__ import annotations

import time
import uuid

from app.db.supabase_client import get_supabase

BUCKET = "user-uploads"
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
SIGNED_URL_TTL_SECONDS = 60 * 60  # 1 hour


def ensure_bucket() -> bool:
    """Create the private bucket if it doesn't exist. Returns True if ready."""
    sb = get_supabase()
    try:
        existing = {b.name for b in sb.storage.list_buckets()}
        if BUCKET not in existing:
            sb.storage.create_bucket(BUCKET, options={"public": False})
        return True
    except Exception:
        return False


def upload_photo(user_id: str, data: bytes, mime: str) -> str:
    """Upload a user photo, return its storage path (not a public URL)."""
    if mime not in ALLOWED_MIME:
        raise ValueError(f"Unsupported image type: {mime}")
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]
    path = f"{user_id}/{int(time.time())}-{uuid.uuid4().hex[:8]}.{ext}"
    get_supabase().storage.from_(BUCKET).upload(
        path, data, file_options={"content-type": mime}
    )
    return path


def signed_url(path: str) -> str | None:
    """Short-lived signed URL for a stored photo (private bucket)."""
    try:
        res = get_supabase().storage.from_(BUCKET).create_signed_url(
            path, SIGNED_URL_TTL_SECONDS
        )
        return res.get("signedURL") or res.get("signedUrl")
    except Exception:
        return None
