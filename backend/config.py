"""
backend/config.py — All settings from environment variables.
No local file paths needed — this is a stateless proxy.

Create a .env file for local dev, or set env vars in Render/Fly.io:

    SATNOGS_TOKEN=your_db_satnogs_token
    JHUAPL_USER=realscience
    JHUAPL_PASS=burstorbust2025!
    CACHE_TTL_SEC=300
    NORAD_ID=64875
"""

from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class Settings:
    # ── JHUAPL flight data ──────────────────────────────
    jhuapl_base_url: str = os.environ.get(
        "JHUAPL_BASE_URL", "https://real-cubesat.jhuapl.edu/data_products/level_1"
    )
    jhuapl_user: str = os.environ.get("JHUAPL_USER", "")
    jhuapl_pass: str = os.environ.get("JHUAPL_PASS", "")

    # ── SatNOGS DB API ──────────────────────────────────
    satnogs_token: str = os.environ.get("SATNOGS_TOKEN", "")
    satnogs_url: str = "https://db.satnogs.org/api/telemetry/"
    norad_id: int = int(os.environ.get("NORAD_ID", "64875"))
    default_sync_days: int = 14
    page_size: int = 500
    max_retries: int = 10
    backoff_sec: float = 1.0

    # ── Cache ───────────────────────────────────────────
    cache_ttl_sec: int = int(os.environ.get("CACHE_TTL_SEC", "1800"))  # 30 min

    # ── Server ──────────────────────────────────────────
    port: int = int(os.environ.get("PORT", "8000"))
    allowed_origins: str = os.environ.get("ALLOWED_ORIGINS", "*")


settings = Settings()