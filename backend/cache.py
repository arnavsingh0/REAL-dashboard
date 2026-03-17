"""
Memory-bounded TTL cache for Render free tier (512MB).

Limits:
  - Max 8 entries (prevents memory creep from many date-range combos)
  - Evicts oldest entry when full
  - Per-entry TTL still applies
"""

from __future__ import annotations
import gc
import threading
import time
from dataclasses import dataclass
from typing import Any

MAX_ENTRIES = 8


@dataclass
class CacheEntry:
    value: Any
    expires_at: float
    created_at: float


class TTLCache:
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, e in self._store.items() if now > e.expires_at]
        for k in expired:
            del self._store[k]
        if expired:
            gc.collect()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry.expires_at:
                del self._store[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            self._evict_expired()

            # Evict oldest if at capacity
            while len(self._store) >= MAX_ENTRIES:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                del self._store[oldest_key]
                gc.collect()

            now = time.time()
            expires = now + (ttl if ttl is not None else self.default_ttl)
            self._store[key] = CacheEntry(value=value, expires_at=expires, created_at=now)

    def invalidate(self, prefix: str = "") -> int:
        with self._lock:
            if not prefix:
                count = len(self._store)
                self._store.clear()
                gc.collect()
                return count
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            gc.collect()
            return len(keys)

    def stats(self) -> dict:
        with self._lock:
            now = time.time()
            total = len(self._store)
            alive = sum(1 for e in self._store.values() if now <= e.expires_at)
            return {"total_entries": total, "alive": alive, "max": MAX_ENTRIES}


cache = TTLCache(default_ttl=300)
