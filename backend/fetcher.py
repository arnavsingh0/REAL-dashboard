"""
On-demand data fetchers for JHUAPL flight data and SatNOGS DB.

Optimized for 512MB RAM / 0.1 CPU (Render free tier):
  - CSVs are downsampled immediately on download (max 3000 rows each)
  - float64 → float32 to halve memory
  - Thread pool capped at 2 workers
  - Total dataset rows capped at 6000 after merge
"""

from __future__ import annotations
import gc
import re
import logging
from io import StringIO
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
import pandas as pd

from config import settings
from cache import cache
from decoder import decode_all

logger = logging.getLogger(__name__)

RAW_COLUMNS = ["timestamp", "payload_hex", "station_id", "station_name"]

MAX_ROWS_PER_CSV = 3000
MAX_DATASET_ROWS = 6000


def _compact_df(df: pd.DataFrame) -> pd.DataFrame:
    """Downsample to MAX_ROWS_PER_CSV and convert floats to float32."""
    if len(df) > MAX_ROWS_PER_CSV:
        step = len(df) // MAX_ROWS_PER_CSV
        df = df.iloc[::step].head(MAX_ROWS_PER_CSV)
    for col in df.select_dtypes("float64").columns:
        df[col] = df[col].astype(np.float32)
    return df


# ── Normalizer ───────────────────────────────────────────────────────

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


# ── JHUAPL raw hex (skipped — L1 CSVs have no payload_hex) ──────────

def fetch_jhuapl(start: str, end: str) -> pd.DataFrame:
    logger.info("JHUAPL raw hex fetch skipped (use L1 tab)")
    return pd.DataFrame(columns=RAW_COLUMNS)


# ── JHUAPL Level-1 fetcher ──────────────────────────────────────────

def _list_jhuapl_day(day_str: str, base: str, auth: tuple) -> list[tuple[str, str]]:
    """Get CSV filenames for one day. Returns [(dataset_key, csv_name), ...]."""
    day_url = f"{base}/{day_str}/"
    try:
        resp = requests.get(day_url, auth=auth, timeout=8)
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
        logger.warning("Dir listing %s failed: %s", day_str, e)
        return []


MAX_CSV_BYTES = 8 * 1024 * 1024  # 8MB — skip downloading anything bigger


def _download_csv(url: str, auth: tuple) -> pd.DataFrame | None:
    """Download a single CSV, immediately downsample and compact."""
    try:
        resp = requests.get(url, auth=auth, timeout=25, stream=True)
        resp.raise_for_status()

        # Check content-length; skip huge files to avoid OOM on free tier
        cl = int(resp.headers.get("content-length", 0))
        if cl > MAX_CSV_BYTES:
            logger.info("Skipping %s (%d MB > %d MB limit)",
                        url.split("/")[-1], cl // 1e6, MAX_CSV_BYTES // 1e6)
            resp.close()
            return None

        # Stream up to MAX_CSV_BYTES
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=512 * 1024):
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_CSV_BYTES:
                logger.info("Truncated %s at %d MB", url.split("/")[-1], total // 1e6)
                break
        resp.close()
        text = b"".join(chunks).decode("utf-8", errors="replace")
        del chunks

        df = pd.read_csv(StringIO(text))
        del text
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

        df = _compact_df(df)
        return df
    except Exception as e:
        logger.warning("CSV download failed %s: %s", url.split("/")[-1], e)
        return None


def get_jhuapl_l1_listings(start: str, end: str) -> dict:
    """Phase 1: directory scan only (fast, no CSV downloads)."""
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

    logger.info("JHUAPL listings: scanning %d days", len(days))

    by_day: dict[str, list[tuple[str, str]]] = {}
    all_keys: set[str] = set()

    with ThreadPoolExecutor(max_workers=min(2, len(days))) as pool:
        futures = {pool.submit(_list_jhuapl_day, d, base, auth): d for d in days}
        for future in as_completed(futures):
            day = futures[future]
            entries = future.result()
            if entries:
                by_day[day] = entries
                all_keys.update(k for k, _ in entries)

    result = {"dataset_names": sorted(all_keys), "by_day": by_day}
    cache.set(cache_key, result, ttl=settings.cache_ttl_sec)
    logger.info("JHUAPL listings: %d datasets across %d days", len(all_keys), len(by_day))
    return result


def get_jhuapl_l1_dataset(start: str, end: str, dataset: str) -> pd.DataFrame:
    """Phase 2: download CSVs for ONE dataset, downsample on ingest."""
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
        logger.info("Dataset %s: no CSVs found", dataset)
        return pd.DataFrame()

    logger.info("Dataset %s: downloading %d CSVs (max %d rows each)", dataset, len(urls), MAX_ROWS_PER_CSV)

    frames = []
    # Sequential download on low-CPU — avoids memory spikes from parallel parsing
    if len(urls) <= 2:
        for u in urls:
            df = _download_csv(u, auth)
            if df is not None:
                frames.append(df)
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_download_csv, u, auth) for u in urls]
            for future in as_completed(futures):
                df = future.result()
                if df is not None:
                    frames.append(df)

    if not frames:
        result = pd.DataFrame()
    else:
        result = pd.concat(frames, ignore_index=True)
        del frames
        gc.collect()

        if "timestamp" in result.columns:
            result = result.sort_values("timestamp").reset_index(drop=True)

        if len(result) > MAX_DATASET_ROWS:
            step = len(result) // MAX_DATASET_ROWS
            result = result.iloc[::step].head(MAX_DATASET_ROWS).reset_index(drop=True)

        result = _compact_df(result)

    cache.set(cache_key, result, ttl=settings.cache_ttl_sec)
    logger.info("Dataset %s: %d rows cached (%.1f MB)", dataset, len(result),
                result.memory_usage(deep=True).sum() / 1e6 if not result.empty else 0)
    gc.collect()
    return result


# ── SatNOGS fetcher ────────────────────────────────────────────────

def fetch_satnogs(start: str, end: str) -> pd.DataFrame:
    if not settings.satnogs_token or len(settings.satnogs_token) < 10:
        logger.warning("SatNOGS fetch skipped: no valid token")
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
                    resp = session.get(url, params=params, timeout=20)
                    if resp.status_code in (401, 403):
                        logger.error("SatNOGS auth failed (%d)", resp.status_code)
                        return pd.DataFrame(columns=RAW_COLUMNS)
                    if resp.status_code == 429:
                        import time as _time
                        _time.sleep(min(float(resp.headers.get("Retry-After", 2)), 5))
                        continue
                    resp.raise_for_status()
                    page = resp.json()
                    break
                except Exception as e:
                    logger.warning("SatNOGS attempt %d: %s", attempt + 1, e)
                    import time as _time
                    _time.sleep(min(settings.backoff_sec * (attempt + 1), 3))

            if page is None:
                break

            for r in page.get("results", []):
                ts = r.get("created") or r.get("timestamp") or r.get("time") or ""
                hx = r.get("frame") or r.get("payload_hex") or r.get("payload") or ""
                hx = str(hx).replace(" ", "").upper()
                if ts and hx:
                    all_rows.append({
                        "timestamp": ts, "payload_hex": hx,
                        "station_id": str(r.get("station_id") or ""),
                        "station_name": str(r.get("observer") or ""),
                    })

            url = page.get("next")
            params = None

        chunk_start = chunk_end

    if all_rows:
        return normalize_raw(pd.DataFrame(all_rows))
    return pd.DataFrame(columns=RAW_COLUMNS)


# ── Combined fetch + decode ────────────────────────────────────────

def get_decoded_data(start: str, end: str, sources: list[str] | None = None) -> dict:
    if sources is None:
        sources = ["jhuapl", "satnogs"]

    cache_key = f"decoded:{start}:{end}:{','.join(sorted(sources))}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("Cache hit: %s", cache_key)
        return cached

    logger.info("Cache miss: %s", cache_key)
    frames = []

    if "jhuapl" in sources:
        try:
            jhuapl_df = fetch_jhuapl(start, end)
            if not jhuapl_df.empty:
                frames.append(jhuapl_df)
        except Exception as e:
            logger.error("JHUAPL fetch failed: %s", e)

    if "satnogs" in sources:
        try:
            satnogs_df = fetch_satnogs(start, end)
            if not satnogs_df.empty:
                frames.append(satnogs_df)
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
