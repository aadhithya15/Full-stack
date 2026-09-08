"""Small input validators used by routes."""
from __future__ import annotations

import re

from app.utils.errors import ApiError

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def require_json(data: dict | None) -> dict:
    if not isinstance(data, dict):
        raise ApiError.invalid_input("Request body must be JSON")
    return data


def valid_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or not _EMAIL_RE.match(email):
        raise ApiError.invalid_input("Please enter a valid email address")
    return email


def valid_password(password: str) -> str:
    password = password or ""
    if len(password) < 8:
        raise ApiError.invalid_input("Password must be at least 8 characters")
    if len(password) > 72:
        raise ApiError.invalid_input("Password is too long (max 72 characters)")
    return password


def valid_full_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ApiError.invalid_input("Please enter your name")
    if len(name) > 80:
        raise ApiError.invalid_input("Name is too long (max 80 characters)")
    return name
