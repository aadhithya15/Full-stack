"""Auth endpoints: /api/auth/register, /login, /me, /logout."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.db import queries
from app.middleware.auth_middleware import require_auth
from app.middleware.rate_limit import rate_limit
from app.services import auth_service
from app.utils.validators import (
    require_json,
    valid_email,
    valid_full_name,
    valid_password,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
@rate_limit("register", per_minute=5)
def register():
    body = require_json(request.get_json(silent=True))
    email = valid_email(body.get("email", ""))
    password = valid_password(body.get("password", ""))
    full_name = valid_full_name(body.get("full_name", ""))

    result = auth_service.register(email, password, full_name)
    return jsonify({"success": True, **result}), 201


@auth_bp.post("/login")
@rate_limit("login", per_minute=5)
def login():
    body = require_json(request.get_json(silent=True))
    email = valid_email(body.get("email", ""))
    password = body.get("password", "")

    result = auth_service.login(email, password)
    return jsonify({"success": True, **result})


@auth_bp.get("/me")
@require_auth
def me():
    profile = queries.get_profile(g.user["id"])
    return jsonify({"success": True, "user": g.user, "profile": profile})


@auth_bp.post("/logout")
@require_auth
def logout():
    # Stateless JWT: the client simply discards the token.
    # (Kept as an endpoint so the frontend flow and future revocation are easy.)
    return jsonify({"success": True, "message": "Logged out"})
