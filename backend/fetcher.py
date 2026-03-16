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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    Raw hex telemetry from JHUAPL — skipped because JHUAPL serves
    Level-1 processed CSVs (no payload_hex column).
    Use fetch_jhuapl_l1() / the /api/jhuapl/* endpoints instead.
    """
    logger.info("JHUAPL raw hex fetch skipped (L1 CSVs have no payload_hex; use JHUAPL L1 tab)")
    return pd.DataFrame(columns=RAW_COLUMNS)


# ── JHUAPL Level-1 fetcher (already-decoded science CSVs) ────────

def _list_jhuapl_day(day_str: str, base: str, auth: tuple) -> list[tuple[str, str]]:
    """Get CSV filenames for one day. Returns [(dataset_key, csv_name), ...]."""
    day_url = f"{base}/{day_str}/"
    try:
        resp = requests.get(day_url, auth=auth, timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        csv_links = re.findall(r'href="([^"]*\.csv)"', resp.text, re.IGNORECASE)
        results = []
        for csv_name in csv_links:
            key = csv_name.rsplit(".", 1)[0]
            if re.match(r"^\d{8}_", key):
                key = key[9:]
            results.append((key, csv_name))
        return results
    except Exception as e:
        logger.warning("Failed dir listing %s: %s", f"{base}/{day_str}/", e)
        return []


def _download_csv(url: str, auth: tuple) -> pd.DataFrame | None:
    """Download and parse a single CSV into a DataFrame."""
    try:
        resp = requests.get(url, auth=auth, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        if df.empty:
            return None

        lower_cols = {c.lower().strip(): c for c in df.columns}
        ts_col = None
        for candidate in ["utc", "timestamp", "time_tag", "time", "created"]:
            if candidate in lower_cols:
                ts_col = lower_cols[candidate]
                break
        if ts_col:
            df = df.rename(columns={ts_col: "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            df = df.dropna(subset=["timestamp"])

        return df
    except Exception as e:
        logger.warning("Failed CSV %s: %s", url, e)
        return None


def get_jhuapl_l1_listings(start: str, end: str) -> dict:
    """
    Phase 1: Just get directory listings (fast, no CSV downloads).
    Returns {dataset_names: [str], by_day: {day: [(key, csv_name)]}}
    """
    cache_key = f"jhuapl_listings:{start}:{end}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    auth = (settings.jhuapl_user, settings.jhuapl_pass)
    base = settings.jhuapl_base_url.rstrip("/")

    start_dt = pd.to_datetime(start, utc=True, errors="coerce")
    end_dt = pd.to_datetime(end, utc=True, errors="coerce")
    if pd.isna(start_dt) or pd.isna(end_dt):
        return {"dataset_names": [], "by_day": {}}

    days = []
    current = start_dt
    while current <= end_dt:
        days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    logger.info("JHUAPL L1 listings: scanning %d days", len(days))

    by_day: dict[str, list[tuple[str, str]]] = {}
    all_keys: set[str] = set()

    with ThreadPoolExecutor(max_workers=min(10, len(days))) as pool:
        futures = {pool.submit(_list_jhuapl_day, d, base, auth): d for d in days}
        for future in as_completed(futures):
            day = futures[future]
            entries = future.result()
            if entries:
                by_day[day] = entries
                all_keys.update(k for k, _ in entries)

    result = {"dataset_names": sorted(all_keys), "by_day": by_day}
    cache.set(cache_key, result, ttl=settings.cache_ttl_sec)
    logger.info("JHUAPL L1 listings: %d datasets across %d days", len(all_keys), len(by_day))
    return result


def get_jhuapl_l1_dataset(start: str, end: str, dataset: str) -> pd.DataFrame:
    """
    Phase 2: Download CSVs for ONE specific dataset type (lazy).
    Much faster than downloading everything upfront.
    """
    cache_key = f"jhuapl_ds:{start}:{end}:{dataset}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("Cache hit: %s", cache_key)
        return cached

    listings = get_jhuapl_l1_listings(start, end)
    auth = (settings.jhuapl_user, settings.jhuapl_pass)
    base = settings.jhuapl_base_url.rstrip("/")

    urls = []
    for day, entries in listings["by_day"].items():
        for key, csv_name in entries:
            if key == dataset:
                urls.append(f"{base}/{day}/{csv_name}")

    if not urls:
        logger.info("JHUAPL L1 dataset %s: no CSVs found", dataset)
        return pd.DataFrame()

    logger.info("JHUAPL L1 dataset %s: downloading %d CSVs", dataset, len(urls))

    frames = []
    with ThreadPoolExecutor(max_workers=min(6, len(urls))) as pool:
        futures = [pool.submit(_download_csv, u, auth) for u in urls]
        for future in as_completed(futures):
            df = future.result()
            if df is not None:
                frames.append(df)

    if not frames:
        result = pd.DataFrame()
    else:
        result = pd.concat(frames, ignore_index=True)
        if "timestamp" in result.columns:
            result = result.sort_values("timestamp").reset_index(drop=True)

    cache.set(cache_key, result, ttl=settings.cache_ttl_sec)
    logger.info("JHUAPL L1 dataset %s: %d rows", dataset, len(result))
    return result


# ── SatNOGS fetcher ────────────────────────────────────────────────

def fetch_satnogs(start: str, end: str) -> pd.DataFrame:
    """
    Fetch telemetry from SatNOGS DB API in 7-day chunks.
    Direct port of the notebook's chunked fetcher — no local storage.
    """
    if not settings.satnogs_token or len(settings.satnogs_token) < 10:
        logger.warning("SatNOGS fetch skipped: no valid token configured")
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
                    resp = session.get(url, params=params, timeout=30)
                    if resp.status_code in (401, 403):
                        logger.error("SatNOGS auth failed (%d) — check SATNOGS_TOKEN", resp.status_code)
                        return pd.DataFrame(columns=RAW_COLUMNS)
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
                    _time.sleep(min(settings.backoff_sec * (attempt + 1), 5))

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