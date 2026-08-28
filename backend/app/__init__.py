"""HueFit backend - Flask application factory."""
import logging
import time

from flask import Flask, g, request
from flask_cors import CORS

from app.config import Config
from app.utils.errors import register_error_handlers


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- CORS: allow the React frontend (dev + deployed origins) ---
    CORS(
        app,
        origins=config_class.ALLOWED_ORIGINS,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    # --- Logging: method, path, status, duration for every request ---
    logging.basicConfig(
        level=logging.DEBUG if config_class.DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Third-party HTTP libraries are extremely chatty at DEBUG level -
    # keep our app logs readable.
    for noisy in ("httpx", "httpcore", "hpack", "h2", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    @app.before_request
    def _start_timer():
        g._start = time.perf_counter()

    @app.after_request
    def _log_request(response):
        duration_ms = (time.perf_counter() - getattr(g, "_start", time.perf_counter())) * 1000
        app.logger.info(
            "%s %s -> %s (%.1f ms)", request.method, request.path, response.status_code, duration_ms
        )
        return response

    # --- Unified error responses ---
    register_error_handlers(app)

    # --- Blueprints ---
    from app.routes.auth_routes import auth_bp
    from app.routes.closet_routes import closet_bp
    from app.routes.fashion_routes import fashion_bp
    from app.routes.health_routes import health_bp
    from app.routes.profile_routes import profile_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(fashion_bp, url_prefix="/api/fashion")
    app.register_blueprint(closet_bp, url_prefix="/api/closet")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")

    app.logger.info(
        "HueFit backend up | env=%s | ai_mock_mode=%s | supabase_configured=%s | origins=%s",
        config_class.ENV,
        config_class.ai_mock_mode(),
        config_class.supabase_configured(),
        config_class.ALLOWED_ORIGINS,
    )
    return app
