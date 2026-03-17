"""
REAL CubeSat Telemetry Dashboard — Stateless FastAPI Proxy

Optimized for Render free tier (512MB RAM, 0.1 CPU).
"""

from __future__ import annotations
import asyncio
import gc
import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

import numpy as np
import pandas as pd

from config import settings
from fields import HEALTH_FIELDS, TIME_FIELDS, field_meta
from cache import cache
from fetcher import get_decoded_data, get_jhuapl_l1_listings, get_jhuapl_l1_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="REAL CubeSat Telemetry API", version="1.0.0")

# GZip responses > 500 bytes — huge savings on JSON payloads over slow networks
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS: allow_credentials=False so allow_origins=["*"] works universally.
# The frontend sends no cookies/auth headers to the backend, so this is correct.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    """Catch-all: ensures CORS headers are on error responses too."""
    logger.error("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


# ── Helpers ─────────────────────────────────────────────────────────

def default_range() -> tuple[str, str]:
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
    limit: int = 2_000,
) -> list[dict]:
    if df is None or df.empty:
        return []

    out = df
    if "timestamp" not in out.columns:
        return []

    ts = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")

    mask = ts.notna()
    if start:
        st = pd.to_datetime(start, utc=True, errors="coerce")
        if not pd.isna(st):
            mask &= ts >= st
    if end:
        et = pd.to_datetime(end, utc=True, errors="coerce")
        if not pd.isna(et):
            if len(end) == 10:
                et = et + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            mask &= ts <= et

    out = out.loc[mask]

    if fields:
        keep = ["timestamp"]
        if "station_name" in out.columns:
            keep.append("station_name")
        keep += [f for f in fields if f in out.columns and f not in keep]
        out = out[keep]

    if len(out) > limit:
        step = max(1, len(out) // limit)
        out = out.iloc[::step].head(limit)

    out = out.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    records = out.to_dict(orient="records")
    for rec in records:
        for k, v in list(rec.items()):
            if isinstance(v, (float, np.floating)):
                if not np.isfinite(v):
                    rec[k] = None
                else:
                    rec[k] = float(v)
            elif isinstance(v, (np.integer,)):
                rec[k] = int(v)
    return records


# ── Endpoints ───────────────────────────────────────────────────────

@app.get("/api/health")
async def get_health(
    start: str | None = Query(None),
    end: str | None = Query(None),
    fields: str | None = Query(None),
    sources: str | None = Query(None),
    limit: int = Query(2_000, ge=1, le=10_000),
):
    s, e = start or default_range()[0], end or default_range()[1]
    data = await asyncio.to_thread(get_decoded_data, s, e, parse_sources(sources))
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    records = df_to_json(data["health_df"], field_list, s, e, limit)
    return {"count": len(records), "beacon_type": "health", "data": records}


@app.get("/api/time")
async def get_time(
    start: str | None = Query(None),
    end: str | None = Query(None),
    fields: str | None = Query(None),
    sources: str | None = Query(None),
    limit: int = Query(2_000, ge=1, le=10_000),
):
    s, e = start or default_range()[0], end or default_range()[1]
    data = await asyncio.to_thread(get_decoded_data, s, e, parse_sources(sources))
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    records = df_to_json(data["time_df"], field_list, s, e, limit)
    return {"count": len(records), "beacon_type": "time", "data": records}


@app.get("/api/fields/health")
async def get_health_fields():
    return {"fields": field_meta(HEALTH_FIELDS)}


@app.get("/api/fields/time")
async def get_time_fields():
    return {"fields": field_meta(TIME_FIELDS)}


@app.get("/api/latest")
async def get_latest(sources: str | None = Query(None)):
    s, e = default_range()
    data = await asyncio.to_thread(get_decoded_data, s, e, parse_sources(sources))

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
    s, e = start or default_range()[0], end or default_range()[1]
    data = await asyncio.to_thread(get_decoded_data, s, e, parse_sources(sources))
    return {
        "date_range": {"start": s, "end": e},
        "raw_frames": data["raw_count"],
        "health_beacons": len(data["health_df"]) if data["health_df"] is not None else 0,
        "time_beacons": len(data["time_df"]) if data["time_df"] is not None else 0,
        "cache": cache.stats(),
    }


@app.post("/api/cache/clear")
async def clear_cache():
    count = cache.invalidate()
    gc.collect()
    return {"cleared": count}


# ── JHUAPL Level-1 endpoints ─────────────────────────────────────────

@app.get("/api/jhuapl/datasets")
async def get_jhuapl_datasets(
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    s, e = start or default_range()[0], end or default_range()[1]
    listings = await asyncio.to_thread(get_jhuapl_l1_listings, s, e)

    datasets = []
    for name in listings["dataset_names"]:
        day_count = sum(
            1 for entries in listings["by_day"].values()
            if any(k == name for k, _ in entries)
        )
        datasets.append({"name": name, "days": day_count})

    datasets.sort(key=lambda d: ("high_spectra" in d["name"], d["name"]))
    return {"datasets": datasets}


@app.get("/api/jhuapl/fields")
async def get_jhuapl_fields(
    dataset: str = Query(...),
    start: str | None = Query(None),
    end: str | None = Query(None),
):
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
    dataset: str = Query(...),
    start: str | None = Query(None),
    end: str | None = Query(None),
    fields: str | None = Query(None),
    limit: int = Query(2_000, ge=1, le=10_000),
):
    s, e = start or default_range()[0], end or default_range()[1]
    df = await asyncio.to_thread(get_jhuapl_l1_dataset, s, e, dataset)

    if df.empty:
        return {"count": 0, "dataset": dataset, "data": []}

    field_list = [f.strip() for f in fields.split(",")] if fields else None
    records = df_to_json(df, field_list, s, e, limit)
    return {"count": len(records), "dataset": dataset, "data": records}


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}
