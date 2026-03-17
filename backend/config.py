"""
backend/config.py — Settings optimized for Render free tier (512MB / 0.1 CPU).
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
    page_size: int = 250
    max_retries: int = 3
    backoff_sec: float = 1.0

    # ── Cache ───────────────────────────────────────────
    cache_ttl_sec: int = int(os.environ.get("CACHE_TTL_SEC", "1800"))

    # ── Server ──────────────────────────────────────────
    port: int = int(os.environ.get("PORT", "8000"))


settings = Settings()
