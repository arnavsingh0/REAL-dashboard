
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
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import numpy as np
import pandas as pd

from config import settings
from fields import HEALTH_FIELDS, TIME_FIELDS, field_meta
from cache import cache
from fetcher import get_decoded_data, get_jhuapl_l1_listings, get_jhuapl_l1_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="REAL CubeSat Telemetry API",
    description="Stateless proxy — fetches from JHUAPL & SatNOGS, decodes, returns JSON.",
    version="1.0.0",
)

# CORS: explicit origins required when using credentials. Strip spaces; default to Render dashboard.
_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
if not _origins or _origins == ["*"]:
    _origins = [
        "https://real-cubesat-dashboard.onrender.com",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
        keep = ["timestamp"]
        if "station_name" in out.columns:
            keep.append("station_name")
        keep += [f for f in fields if f in out.columns and f not in keep]
        out = out[keep]

    if len(out) > limit:
        step = max(1, len(out) // limit)
        out = out.iloc[::step].head(limit)

    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = out.replace([np.inf, -np.inf], np.nan)
    records = out.to_dict(orient="records")
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                rec[k] = None
    return records


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

    data = await asyncio.to_thread(get_decoded_data, s, e, src)
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

    data = await asyncio.to_thread(get_decoded_data, s, e, src)
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
    data = await asyncio.to_thread(get_decoded_data, s, e, src)

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
    data = await asyncio.to_thread(get_decoded_data, s, e, src)

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


# ── JHUAPL Level-1 endpoints ─────────────────────────────────────────

@app.get("/api/jhuapl/datasets")
async def get_jhuapl_datasets(
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    """List available JHUAPL L1 dataset names (fast — directory scan only)."""
    s, e = start or default_range()[0], end or default_range()[1]
    listings = await asyncio.to_thread(get_jhuapl_l1_listings, s, e)

    datasets = []
    for name in listings["dataset_names"]:
        day_count = sum(
            1 for entries in listings["by_day"].values()
            if any(k == name for k, _ in entries)
        )
        datasets.append({"name": name, "days": day_count, "numeric_columns": []})

    datasets.sort(key=lambda d: ("high_spectra" in d["name"], d["name"]))

    return {"datasets": datasets}


@app.get("/api/jhuapl/fields")
async def get_jhuapl_fields(
    dataset: str = Query(...),
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    """Return column metadata for a specific JHUAPL L1 dataset (downloads CSVs)."""
    s, e = start or default_range()[0], end or default_range()[1]
    df = await asyncio.to_thread(get_jhuapl_l1_dataset, s, e, dataset)

    fields = []
    for col in df.columns:
        if col.startswith("_") or col == "timestamp":
            continue
        fields.append({
            "name": col,
            "units": "",
            "thresholds": {},
            "signed": False,
            "numeric": bool(pd.api.types.is_numeric_dtype(df[col])),
        })

    return {"fields": {dataset: fields}, "rows": len(df)}


@app.get("/api/jhuapl/data")
async def get_jhuapl_data(
    dataset: str = Query(..., description="Dataset name, e.g. low_rates_L1"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    fields: str | None = Query(None),
    limit: int = Query(10_000, ge=1, le=100_000),
):
    """Return data from a specific JHUAPL L1 dataset."""
    s, e = start or default_range()[0], end or default_range()[1]
    df = await asyncio.to_thread(get_jhuapl_l1_dataset, s, e, dataset)

    if df.empty:
        return {"count": 0, "dataset": dataset, "data": []}

    field_list = [f.strip() for f in fields.split(",")] if fields else None
    records = df_to_json(df, field_list, s, e, limit)

    return {
        "count": len(records),
        "dataset": dataset,
        "data": records,
    }


# ── Health check (for Render / Fly.io) ──────────────────────────────

@app.get("/health")
async def healthcheck():
    return {"status": "ok"}