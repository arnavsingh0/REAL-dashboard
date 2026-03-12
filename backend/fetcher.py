"""
On-demand data fetchers for JHUAPL flight data and SatNOGS DB.
No local storage — fetch, decode, cache in memory, return.

JHUAPL: CSVs in date-indexed directories (basic auth)
SatNOGS: Paginated JSON API (token auth)
"""

from __future__ import annotations
import re
import logging
from io import StringIO
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

from config import settings
from cache import cache
from decoder import decode_all

logger = logging.getLogger(__name__)

RAW_COLUMNS = ["timestamp", "payload_hex", "station_id", "station_name"]


# ── Normalizer (same logic as notebook) ─────────────────────────────

def normalize_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)
    out = df.copy()
    for col in RAW_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[RAW_COLUMNS].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out["payload_hex"] = out["payload_hex"].astype(str).str.replace(" ", "", regex=False).str.upper()
    out["station_id"] = out["station_id"].astype(str)
    out["station_name"] = out["station_name"].astype(str)
    out = out.dropna(subset=["timestamp"])
    out = out[out["payload_hex"] != ""]
    return out.drop_duplicates(subset=["timestamp", "payload_hex"]).reset_index(drop=True)


def iso_z(dt) -> str:
    d = pd.to_datetime(dt, utc=True, errors="coerce")
    return "" if pd.isna(d) else d.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── JHUAPL fetcher ──────────────────────────────────────────────────

def fetch_jhuapl(start: str, end: str) -> pd.DataFrame:
    """
    Fetch CSVs from JHUAPL's date-indexed flight_data directories.

    Directory structure:
        /flight_data/20250930/
        /flight_data/20251001/
        ...
    Each contains CSV files with parsed telemetry.
    """
    auth = (settings.jhuapl_user, settings.jhuapl_pass)
    base = settings.jhuapl_base_url.rstrip("/")

    start_dt = pd.to_datetime(start, utc=True, errors="coerce")
    end_dt = pd.to_datetime(end, utc=True, errors="coerce")

    if pd.isna(start_dt) or pd.isna(end_dt):
        logger.warning("Invalid date range for JHUAPL fetch: %s → %s", start, end)
        return pd.DataFrame(columns=RAW_COLUMNS)

    all_frames = []
    current = start_dt

    while current <= end_dt:
        day_str = current.strftime("%Y%m%d")
        day_url = f"{base}/{day_str}/"

        try:
            resp = requests.get(day_url, auth=auth, timeout=30)
            if resp.status_code == 404:
                current += timedelta(days=1)
                continue
            resp.raise_for_status()

            # Parse directory listing for CSV links
            csv_links = re.findall(r'href="([^"]*\.csv)"', resp.text, re.IGNORECASE)

            for csv_name in csv_links:
                # Skip quicklook or non-telemetry files if needed
                csv_url = f"{day_url}{csv_name}"

                try:
                    csv_resp = requests.get(csv_url, auth=auth, timeout=60)
                    csv_resp.raise_for_status()

                    df = pd.read_csv(StringIO(csv_resp.text))

                    # ── Column mapping ──────────────────────────────
                    # JHUAPL CSVs may use different column names.
                    # Adapt this mapping based on actual file headers.
                    # Common patterns from the Autoplot instructions:
                    #   utc, payload_hex, frame, etc.

                    col_map = {}
                    lower_cols = {c.lower().strip(): c for c in df.columns}

                    # timestamp
                    for candidate in ["utc", "timestamp", "time", "created"]:
                        if candidate in lower_cols:
                            col_map[lower_cols[candidate]] = "timestamp"
                            break

                    # payload hex
                    for candidate in ["payload_hex", "frame", "payload", "raw_hex", "hex"]:
                        if candidate in lower_cols:
                            col_map[lower_cols[candidate]] = "payload_hex"
                            break

                    if "timestamp" not in col_map.values() or "payload_hex" not in col_map.values():
                        # Not a raw telemetry CSV — skip
                        continue

                    df = df.rename(columns=col_map)
                    df["station_id"] = "JHUAPL"
                    df["station_name"] = f"JHUAPL/{csv_name}"

                    all_frames.append(df)
                    logger.debug("Fetched %s: %d rows", csv_url, len(df))

                except Exception as e:
                    logger.warning("Failed CSV %s: %s", csv_url, e)

        except Exception as e:
            logger.warning("Failed dir listing %s: %s", day_url, e)

        current += timedelta(days=1)

    if all_frames:
        return normalize_raw(pd.concat(all_frames, ignore_index=True))
    return pd.DataFrame(columns=RAW_COLUMNS)


# ── SatNOGS fetcher ────────────────────────────────────────────────

def fetch_satnogs(start: str, end: str) -> pd.DataFrame:
    """
    Fetch telemetry from SatNOGS DB API in 7-day chunks.
    Direct port of the notebook's chunked fetcher — no local storage.
    """
    if not settings.satnogs_token:
        logger.warning("SatNOGS fetch skipped: no token configured")
        return pd.DataFrame(columns=RAW_COLUMNS)

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Authorization": f"Token {settings.satnogs_token}",
    })

    start_dt = pd.to_datetime(start, utc=True, errors="coerce")
    end_dt = pd.to_datetime(end, utc=True, errors="coerce")

    if pd.isna(start_dt):
        start_dt = datetime.now(timezone.utc) - timedelta(days=settings.default_sync_days)
    if pd.isna(end_dt):
        end_dt = datetime.now(timezone.utc)

    # ensure datetime objects
    start_dt = start_dt.to_pydatetime() if hasattr(start_dt, "to_pydatetime") else start_dt
    end_dt = end_dt.to_pydatetime() if hasattr(end_dt, "to_pydatetime") else end_dt

    chunk_days = 7
    chunk_start = start_dt
    all_rows = []

    while chunk_start < end_dt:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end_dt)

        url = settings.satnogs_url
        params = {
            "satellite": str(settings.norad_id),
            "start": iso_z(chunk_start),
            "end": iso_z(chunk_end),
            "page_size": str(settings.page_size),
        }

        while url:
            page = None
            for attempt in range(settings.max_retries):
                try:
                    resp = session.get(url, params=params, timeout=60)
                    if resp.status_code == 429:
                        wait = resp.headers.get("Retry-After")
                        wait = float(wait) if wait else settings.backoff_sec * (attempt + 1) * 2
                        import time as _time
                        _time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    page = resp.json()
                    break
                except Exception as e:
                    logger.warning("SatNOGS attempt %d: %s", attempt + 1, e)
                    import time as _time
                    _time.sleep(settings.backoff_sec * (attempt + 1))

            if page is None:
                logger.error("SatNOGS chunk failed: %s → %s", iso_z(chunk_start), iso_z(chunk_end))
                break

            for r in page.get("results", []):
                ts = r.get("created") or r.get("timestamp") or r.get("time") or ""
                hx = r.get("frame") or r.get("payload_hex") or r.get("payload") or ""
                hx = str(hx).replace(" ", "").upper()
                if ts and hx:
                    all_rows.append({
                        "timestamp": ts,
                        "payload_hex": hx,
                        "station_id": str(r.get("station_id") or r.get("observer_id") or ""),
                        "station_name": str(r.get("observer") or r.get("station_name") or ""),
                    })

            url = page.get("next")
            params = None  # next URL has params baked in

        chunk_start = chunk_end

    if all_rows:
        return normalize_raw(pd.DataFrame(all_rows))
    return pd.DataFrame(columns=RAW_COLUMNS)


# ── Combined fetch + decode with caching ────────────────────────────

def get_decoded_data(
    start: str,
    end: str,
    sources: list[str] | None = None,
) -> dict:
    """
    Main entry point for the API. Returns cached or freshly-fetched
    decoded telemetry as DataFrames.

    Returns:
        {
            "health_df": pd.DataFrame,
            "time_df": pd.DataFrame,
            "other_df": pd.DataFrame,
            "raw_count": int,
            "sources_used": [...],
        }
    """
    if sources is None:
        sources = ["jhuapl", "satnogs"]

    cache_key = f"decoded:{start}:{end}:{','.join(sorted(sources))}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("Cache hit: %s", cache_key)
        return cached

    logger.info("Cache miss — fetching: %s", cache_key)

    frames = []

    if "jhuapl" in sources:
        try:
            jhuapl_df = fetch_jhuapl(start, end)
            if not jhuapl_df.empty:
                frames.append(jhuapl_df)
                logger.info("JHUAPL: fetched %d raw rows", len(jhuapl_df))
        except Exception as e:
            logger.error("JHUAPL fetch failed: %s", e)

    if "satnogs" in sources:
        try:
            satnogs_df = fetch_satnogs(start, end)
            if not satnogs_df.empty:
                frames.append(satnogs_df)
                logger.info("SatNOGS: fetched %d raw rows", len(satnogs_df))
        except Exception as e:
            logger.error("SatNOGS fetch failed: %s", e)

    if frames:
        raw_df = pd.concat(frames, ignore_index=True)
        raw_df = raw_df.drop_duplicates(subset=["timestamp", "payload_hex"]).sort_values("timestamp").reset_index(drop=True)
    else:
        raw_df = pd.DataFrame(columns=RAW_COLUMNS)

    health_df, time_df, other_df = decode_all(raw_df)

    result = {
        "health_df": health_df,
        "time_df": time_df,
        "other_df": other_df,
        "raw_count": len(raw_df),
        "sources_used": sources,
    }

    cache.set(cache_key, result, ttl=settings.cache_ttl_sec)
    return result