"""AI provider diagnostic - finds out exactly what is available to YOUR keys.

Run:  python diagnose_ai.py

It calls each provider's list-models endpoint and prints which models your
key can use, so we always target a model that actually exists.
"""
from __future__ import annotations

import sys

import requests

from app.config import Config


def check_gemini() -> None:
    print("--- GEMINI ---")
    if Config.is_placeholder(Config.GEMINI_API_KEY):
        print("  key: placeholder (skipped)")
        return
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": Config.GEMINI_API_KEY, "pageSize": 50},
            timeout=20,
        )
        print(f"  list-models HTTP status: {r.status_code}")
        if r.status_code != 200:
            print("  body:", r.text[:300])
            return
        models = r.json().get("models", [])
        usable = [
            m["name"].split("/")[-1]
            for m in models
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        print(f"  models supporting generateContent ({len(usable)}):")
        for name in usable:
            print("   -", name)
    except Exception as e:
        print("  ERROR:", type(e).__name__, str(e)[:200])


def check_groq() -> None:
    print("--- GROQ ---")
    if Config.is_placeholder(Config.GROQ_API_KEY):
        print("  key: placeholder (skipped)")
        return
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
            timeout=20,
        )
        print(f"  list-models HTTP status: {r.status_code}")
        if r.status_code != 200:
            print("  body:", r.text[:300])
            return
        models = [m["id"] for m in r.json().get("data", [])]
        print(f"  available models ({len(models)}):")
        for name in sorted(models):
            print("   -", name)
    except Exception as e:
        print("  ERROR:", type(e).__name__, str(e)[:200])


if __name__ == "__main__":
    print("HueFit - AI provider diagnostic")
    print("=" * 50)
    check_gemini()
    print()
    check_groq()
    print("=" * 50)
    print("Send this output to your assistant / compare with .env model settings.")
    sys.exit(0)
