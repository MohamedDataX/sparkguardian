"""Application settings, loaded from environment (.env supported)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; env vars still work without it
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Runtime configuration. Everything overridable via env vars."""

    # HMAC secret used to sign license tokens. MUST be set in production.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-change-me")

    # Bearer token protecting the admin API/dashboard.
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "admin-dev-token")

    # SQLite database location.
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "sparkguardian.db"))

    # Public base URL of this app (used in generated links).
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "http://localhost:8000")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
