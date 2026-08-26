"""Health & meta endpoints.

GET /api/health is used by:
  - the frontend to confirm the API base URL is correct,
  - UptimeRobot/cron-job.org pings to keep the Render free instance awake,
  - you, to check mock-mode / config state at a glance.
"""
from flask import Blueprint, jsonify

from app.config import Config

health_bp = Blueprint("health", __name__)

API_VERSION = "0.1.0"  # Phase 1


@health_bp.get("/health")
def health():
    return jsonify(
        {
            "success": True,
            "service": "huefit-api",
            "version": API_VERSION,
            "status": "ok",
            "ai_mock_mode": Config.ai_mock_mode(),
            "supabase_configured": Config.supabase_configured(),
        }
    )


@health_bp.get("/")
def index():
    return jsonify(
        {
            "success": True,
            "service": "huefit-api",
            "message": "HueFit API â€” Your colours. Your fit.",
            "docs": "See README.md / Postman collection for endpoints.",
        }
    )
