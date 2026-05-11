"""Configuracion central del proyecto."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
REPORTS_DIR = ROOT / "reports"
GARTH_TOKENS_DIR = CACHE_DIR / "garth"

CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
GARTH_TOKENS_DIR.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "").strip()
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7").strip()


def require_garmin_credentials() -> None:
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise SystemExit(
            "Faltan credenciales de Garmin. Copia .env.example a .env "
            "y rellena GARMIN_EMAIL y GARMIN_PASSWORD."
        )
