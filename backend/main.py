
"""
REAL CubeSat Telemetry Dashboard — Stateless FastAPI Proxy

No local storage. Fetches from JHUAPL + SatNOGS on demand,
decodes in memory, caches with TTL, returns JSON.

Run locally:
    cd backend
    uvicorn main:app --reload --port 8000

Deploy:
    Set env vars (SATNOGS_TOKEN, JHUAPL_USER, JHUAPL_PASS)
    and deploy the Dockerfile to Render / Fly.io.

Endpoints:
    GET  /api/health?start=&end=&fields=&sources=&limit=
    GET  /api/time?start=&end=&fields=&sources=&limit=
    GET  /api/fields/health
    GET  /api/fields/time
    GET  /api/latest?sources=
    GET  /api/stats?start=&end=&sources=
    POST /api/cache/clear
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import pandas as pd

from config import settings
from fields import HEALTH_FIELDS, TIME_FIELDS, field_meta
from cache import cache
from fetcher import get_decoded_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="REAL CubeSat Telemetry API",
    description="Stateless proxy — fetches from JHUAPL & SatNOGS, decodes, returns JSON.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────

def default_range() -> tuple[str, str]:
    """Default to last 14 days if no range specified."""
    now = datetime.now(timezone.utc)
    end = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=settings.default_sync_days)).strftime("%Y-%m-%d")
    return start, end


def parse_sources(sources_str: str | None) -> list[str]:
    if not sources_str:
        return ["jhuapl", "satnogs"]
    return [s.strip().lower() for s in sources_str.split(",") if s.strip()]


def df_to_json(
    df: pd.DataFrame,
    fields: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 10_000,
) -> list[dict]:
    if df is None or df.empty:
        return []

    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")

    if start:
        st = pd.to_datetime(start, utc=True, errors="coerce")
        if not pd.isna(st):
            out = out[out["timestamp"] >= st]
    if end:
        et = pd.to_datetime(end, utc=True, errors="coerce")
        if not pd.isna(et):
            if len(end) == 10:  # date-only → include full day
                et = et + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            out = out[out["timestamp"] <= et]

    if fields:
        keep = ["timestamp", "station_name"] + [f for f in fields if f in out.columns]
        out = out[keep]

    out = out.tail(limit)
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return out.where(out.notna(), None).to_dict(orient="records")


# ── Endpoints ───────────────────────────────────────────────────────

@app.get("/api/health")
async def get_health(
    start: str | None = Query(None, description="ISO start date, e.g. 2026-01-01"),
    end: str | None = Query(None, description="ISO end date, e.g. 2026-01-14"),
    fields: str | None = Query(None, description="Comma-separated field names"),
    sources: str | None = Query(None, description="Comma-separated: jhuapl,satnogs"),
    limit: int = Query(10_000, ge=1, le=100_000),
):
    """Fetch and decode health beacon telemetry."""
    s, e = start or default_range()[0], end or default_range()[1]
    src = parse_sources(sources)

    data = get_decoded_data(s, e, src)
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    records = df_to_json(data["health_df"], field_list, s, e, limit)

    return {
        "count": len(records),
        "beacon_type": "health",
        "sources": data["sources_used"],
        "data": records,
    }


@app.get("/api/time")
async def get_time(
    start: str | None = Query(None),
    end: str | None = Query(None),
    fields: str | None = Query(None),
    sources: str | None = Query(None),
    limit: int = Query(10_000, ge=1, le=100_000),
):
    """Fetch and decode time beacon telemetry."""
    s, e = start or default_range()[0], end or default_range()[1]
    src = parse_sources(sources)

    data = get_decoded_data(s, e, src)
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    records = df_to_json(data["time_df"], field_list, s, e, limit)

    return {
        "count": len(records),
        "beacon_type": "time",
        "sources": data["sources_used"],
        "data": records,
    }


@app.get("/api/fields/health")
async def get_health_fields():
    """Return metadata for all health beacon fields (names, units, thresholds)."""
    return {"fields": field_meta(HEALTH_FIELDS)}


@app.get("/api/fields/time")
async def get_time_fields():
    """Return metadata for all time beacon fields."""
    return {"fields": field_meta(TIME_FIELDS)}


@app.get("/api/latest")
async def get_latest(
    sources: str | None = Query(None),
):
    """Return the most recent decoded value for every field."""
    s, e = default_range()
    src = parse_sources(sources)
    data = get_decoded_data(s, e, src)

    result = {"health": {}, "time": {}}

    health_df = data["health_df"]
    if health_df is not None and not health_df.empty:
        latest = health_df.iloc[-1]
        result["health"] = {
            "timestamp": str(latest.get("timestamp", "")),
            "values": {
                f[0]: {
                    "value": latest.get(f[0]),
                    "units": f[5],
                    "thresholds": {k: v for k, v in f[6].items() if k in ("RL", "YL", "Nom", "YH", "RH")},
                }
                for f in HEALTH_FIELDS if f[0] != "sync_word"
            },
        }

    time_df = data["time_df"]
    if time_df is not None and not time_df.empty:
        latest = time_df.iloc[-1]
        result["time"] = {
            "timestamp": str(latest.get("timestamp", "")),
            "values": {
                f[0]: {"value": latest.get(f[0]), "units": f[5]}
                for f in TIME_FIELDS if f[0] != "sync_word"
            },
        }

    return result


@app.get("/api/stats")
async def get_stats(
    start: str | None = Query(None),
    end: str | None = Query(None),
    sources: str | None = Query(None),
):
    """Summary statistics for the requested window."""
    s, e = start or default_range()[0], end or default_range()[1]
    src = parse_sources(sources)
    data = get_decoded_data(s, e, src)

    return {
        "date_range": {"start": s, "end": e},
        "sources": data["sources_used"],
        "raw_frames": data["raw_count"],
        "health_beacons": len(data["health_df"]) if data["health_df"] is not None else 0,
        "time_beacons": len(data["time_df"]) if data["time_df"] is not None else 0,
        "cache": cache.stats(),
    }


@app.post("/api/cache/clear")
async def clear_cache():
    """Manually invalidate all cached data."""
    count = cache.invalidate()
    return {"cleared": count, "message": f"Cleared {count} cache entries"}


# ── Health check (for Render / Fly.io) ──────────────────────────────

@app.get("/health")
async def healthcheck():
    return {"status": "ok"}