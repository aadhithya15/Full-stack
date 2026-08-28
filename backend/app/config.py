"""HueFit backend configuration.

All values come from environment variables (.env in development,
dashboard env vars in production). Never hardcode secrets here.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


class Config:
    # --- Flask ---
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = ENV == "development"
    PORT = int(os.getenv("PORT", "5000"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024  # photo uploads

    # --- CORS ---
    ALLOWED_ORIGINS = _origins()

    # --- Supabase (Phase 2) ---
    SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL_HERE")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_ROLE_KEY_HERE")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "YOUR_JWT_SECRET_HERE")

    # --- AI providers (Phase 5 â€” placeholders until real keys arrive) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "PLACEHOLDER_REPLACE_WHEN_AVAILABLE")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "PLACEHOLDER_REPLACE_WHEN_AVAILABLE")

    @staticmethod
    def is_placeholder(value: str) -> bool:
        """True if an env value is still an unfilled placeholder."""
        if not value:
            return True
        upper = value.upper()
        return "PLACEHOLDER" in upper or upper.startswith("YOUR_")

    @classmethod
    def ai_mock_mode(cls) -> bool:
        """Mock mode is ON until at least one real AI key is provided."""
        return cls.is_placeholder(cls.GEMINI_API_KEY) and cls.is_placeholder(cls.GROQ_API_KEY)

    @classmethod
    def supabase_configured(cls) -> bool:
        return not cls.is_placeholder(cls.SUPABASE_URL) and not cls.is_placeholder(
            cls.SUPABASE_SERVICE_KEY
        )
