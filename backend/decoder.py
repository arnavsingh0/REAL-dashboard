"""
REAL CubeSat beacon decoder.
Extracts frames from raw hex payloads, splits by beacon type,
and decodes fields using bit-level slicing.

Direct port of notebook cells: hex_to_bytes, bitslice, to_signed,
decode_table, and the frame-extraction loop.
"""

from __future__ import annotations
import math
from datetime import datetime, timezone
import pandas as pd

from fields import (
    SYNC_WORD, HEALTH_BEACON_LENGTH, HEALTH_BEACON_TRIM,
    TIME_BEACON_LENGTH, TIME_BEACON_TRIM,
    HEALTH_FIELDS, TIME_FIELDS,
)


# ── Low-level helpers ───────────────────────────────────────────────

def hex_to_bytes(hex_text: str) -> bytes:
    try:
        return bytes.fromhex(str(hex_text).strip().replace(" ", ""))
    except Exception:
        return b""


def bitslice(frame: bytes, bit_start: int, bit_count: int) -> int | None:
    first_byte = bit_start // 8
    last_byte = (bit_start + bit_count - 1) // 8
    if last_byte >= len(frame):
        return None
    value = int.from_bytes(frame[first_byte : last_byte + 1], "big", signed=False)
    total_bits = (last_byte - first_byte + 1) * 8
    shift = total_bits - ((bit_start % 8) + bit_count)
    mask = (1 << bit_count) - 1
    return (value >> shift) & mask


def to_signed(raw: int | None, bit_count: int) -> int | None:
    if raw is None:
        return None
    signbit = 1 << (bit_count - 1)
    return raw - (1 << bit_count) if (raw & signbit) else raw


# ── Frame extraction ────────────────────────────────────────────────

class ExtractedFrames:
    __slots__ = (
        "health_frames", "health_timestamps", "health_stations", "health_hex",
        "time_frames", "time_timestamps", "time_stations", "time_hex",
        "other_rows", "total",
    )
    def __init__(self):
        self.health_frames, self.health_timestamps = [], []
        self.health_stations, self.health_hex = [], []
        self.time_frames, self.time_timestamps = [], []
        self.time_stations, self.time_hex = [], []
        self.other_rows = []
        self.total = 0


def extract_frames(raw_df: pd.DataFrame) -> ExtractedFrames:
    result = ExtractedFrames()
    if raw_df is None or raw_df.empty:
        return result

    sync_hex = SYNC_WORD.hex().upper()
    candidates = raw_df[
        raw_df["payload_hex"].astype(str).str.contains(sync_hex, regex=False, na=False)
    ]

    for row in candidates.itertuples(index=False):
        payload = hex_to_bytes(row.payload_hex)
        if not payload:
            continue

        positions = []
        pos = payload.find(SYNC_WORD)
        while pos != -1:
            positions.append(pos)
            pos = payload.find(SYNC_WORD, pos + 1)
        if not positions:
            continue

        positions.append(len(payload))

        for i in range(len(positions) - 1):
            frame = payload[positions[i] : positions[i + 1]]
            flen = len(frame)
            if flen == 0:
                continue

            result.total += 1

            if flen == HEALTH_BEACON_LENGTH:
                trimmed = frame[:-HEALTH_BEACON_TRIM]
                result.health_frames.append(trimmed)
                result.health_timestamps.append(row.timestamp)
                result.health_stations.append(getattr(row, "station_name", ""))
                result.health_hex.append(trimmed.hex().upper())

            elif flen == TIME_BEACON_LENGTH:
                trimmed = frame[:-TIME_BEACON_TRIM]
                result.time_frames.append(trimmed)
                result.time_timestamps.append(row.timestamp)
                result.time_stations.append(getattr(row, "station_name", ""))
                result.time_hex.append(trimmed.hex().upper())

            else:
                result.other_rows.append({
                    "timestamp": row.timestamp,
                    "station_name": getattr(row, "station_name", ""),
                    "len_bytes": flen,
                    "hex": frame.hex().upper(),
                })

    return result


# ── Decode table ────────────────────────────────────────────────────

def decode_table(
    frames: list[bytes],
    timestamps: list,
    stations: list[str],
    frame_hex: list[str],
    fields: list[tuple],
) -> pd.DataFrame:
    rows = []
    for frame, ts, st, hx in zip(frames, timestamps, stations, frame_hex):
        rec = {"timestamp": ts, "station_name": st, "hex": hx}
        for f in fields:
            name, bit_start, bit_count, scale, offset, units, *rest = f
            meta = rest[-1] if (rest and isinstance(rest[-1], dict)) else {}
            signed = bool(meta.get("_signed"))

            raw = bitslice(frame, bit_start, bit_count)
            if raw is None:
                rec[name] = float("nan")
                continue
            if signed:
                raw = to_signed(raw, bit_count)
            rec[name] = raw * scale + offset
        rows.append(rec)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


# ── High-level: raw hex → decoded DataFrames ────────────────────────

def decode_all(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ef = extract_frames(raw_df)
    health_df = decode_table(
        ef.health_frames, ef.health_timestamps,
        ef.health_stations, ef.health_hex, HEALTH_FIELDS,
    )
    time_df = decode_table(
        ef.time_frames, ef.time_timestamps,
        ef.time_stations, ef.time_hex, TIME_FIELDS,
    )
    other_df = pd.DataFrame(ef.other_rows)
    return health_df, time_df, other_df