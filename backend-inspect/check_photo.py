"""Phase 6 LIVE verification - skin tone detection from a real photo.

Usage:
    python check_photo.py path\\to\\photo.jpg

Give it any selfie/portrait photo (jpg/png/webp). It runs the full
detection chain (Gemini Vision -> Pillow fallback) and prints the result.
If you don't pass a file, it generates a synthetic skin-coloured image
so you can still verify the pipeline.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path


def main() -> int:
    from app import create_app

    app = create_app()
    with app.app_context():
        from app.services.skin_tone_service import (
            _detect_with_gemini,
            _detect_with_pillow,
            detect_skin_tone,
        )

        if len(sys.argv) > 1:
            p = Path(sys.argv[1])
            if not p.exists():
                print(f"File not found: {p}")
                return 1
            data = p.read_bytes()
            mime = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp",
            }.get(p.suffix.lower(), "image/jpeg")
            print(f"Photo: {p.name} ({len(data)//1024} KB, {mime})")
        else:
            from PIL import Image

            img = Image.new("RGB", (240, 320), (193, 140, 100))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            data = buf.getvalue()
            mime = "image/jpeg"
            print("No photo given - using a synthetic wheatish-tone test image.")
            print("(Tip: python check_photo.py your_selfie.jpg)")

        print("=" * 50)
        print("1) Gemini Vision (primary):")
        v = _detect_with_gemini(data, mime)
        print("   ->", v if v else "unavailable (falls back to Pillow)")

        print("2) Pillow pixel analysis (fallback):")
        pw = _detect_with_pillow(data)
        print("   ->", pw if pw else "could not analyse")

        print("3) Full chain result (what /analyze will use):")
        final = detect_skin_tone(data, mime)
        print("   ->", final)
        print("=" * 50)
        print("Phase 6 verified." if final else "Something went wrong.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
