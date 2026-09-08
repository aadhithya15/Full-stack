"""Local development entry point.

    python run.py

Production uses gunicorn instead (see render.yaml / Procfile):
    gunicorn "app:create_app()" -b 0.0.0.0:$PORT
"""
from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
